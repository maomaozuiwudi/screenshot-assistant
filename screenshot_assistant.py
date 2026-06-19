#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
截图助手 - 小红书分镜截图工具
锁定9:16比例截图，分镜描述管理，暂存筛选，Ken Burns动画预览，AI截图来源建议
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageGrab, ImageTk
import os
import json
import time
import re
from pathlib import Path

APP_DIR = Path(__file__).parent
DATA_FILE = APP_DIR / "storyboards.json"
DEFAULT_SAVE_DIR = APP_DIR / "captures"
ASPECT_W, ASPECT_H = 9, 16
OVERLAY_ALPHA = 0.35
BORDER_COLOR = "#FF2442"
CORNER_SIZE = 12

PRESET_SIZES = {
    "小 (540×960)": (540, 960),
    "中 (720×1280)": (720, 1280),
    "大 (1080×1920)": (1080, 1920),
}

# ---- AI 截图来源分析 ----
SOURCE_RULES = [
    (r"产品|商品|实物|包装|开箱|包裹", "电商平台", "淘宝/京东/拼多多商品详情页、1688供应商页面截图"),
    (r"效果|使用|前后|对比|before|after", "效果展示", "小红书种草笔记/抖音评测视频截图，找真实用户反馈"),
    (r"界面|屏幕|APP|软件|网页|页面|截图|操作", "软件界面", "用本工具直接截取软件/网页界面"),
    (r"穿搭|衣服|鞋|包|配饰|上身|试穿", "穿搭展示", "小红书穿搭笔记、品牌官方lookbook截图"),
    (r"美食|菜|吃|餐厅|外卖|食材|厨房|烹饪", "美食场景", "大众点评/小红书美食笔记、自己拍摄食物"),
    (r"数据|图表|统计|报告|分析|趋势|数字", "数据图表", "行业报告PDF截图、Excel图表导出、百度指数"),
    (r"教程|步骤|方法|技巧|怎么|如何|攻略", "教程示意", "自己操作录屏后截图关键步骤，或网上教程截图"),
    (r"场景|环境|室内|室外|背景|氛围|空间", "场景环境", "Unsplash/Pexels免费图库、自己拍摄场景照"),
    (r"人物|模特|表情|动作|人脸|自拍|人像", "人物素材", "自己拍摄或授权肖像照，AI生成人像（注意合规）"),
    (r"文字|文案|标题|封面|海报|卡片|排版", "设计素材", "用Canva/稿定设计制作，或本工具截取排版参考"),
    (r"价格|价格表|费用|报价|预算|成本|收费", "价格信息", "截取官网定价页、竞品价格对比表"),
    (r"酒店|民宿|旅行|景点|旅游|风景|打卡", "旅行场景", "携程/小红书旅行笔记、自己旅行拍摄"),
    (r"数码|电子|手机|电脑|耳机|相机|科技", "数码产品", "品牌官网产品页、京东/天猫商品详情页截图"),
    (r"美妆|护肤|化妆|口红|粉底|面膜|精华", "美妆护肤", "品牌官网/天猫旗舰店、小红书美妆笔记截图"),
    (r"家居|家具|装修|收纳|房间|客厅|卧室", "家居场景", "小红书家居博主笔记、宜家/淘宝家具详情页截图"),
]


def analyze_description(desc):
    results = []
    for pattern, source, tip in SOURCE_RULES:
        if re.search(pattern, desc):
            results.append((source, tip))
    return results if results else [("通用素材", "根据描述内容，去相关网站或自己拍摄对应画面")]


# ---- 截图叠加窗口 ----
class Overlay:
    def __init__(self, app):
        self.app = app
        self.width, self.height = 540, 960
        self.x, self.y = 100, 50
        self.active = False
        self._drag = None
        self._resize = None

        self.win = tk.Toplevel(app.root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", OVERLAY_ALPHA)

        self.canvas = tk.Canvas(self.win, highlightthickness=0, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.win.bind("<Escape>", lambda e: self.hide())
        self.win.bind("<space>", lambda e: self.capture())
        self.win.bind("<Return>", lambda e: self.capture())

        self.win.withdraw()

    def _draw(self):
        self.canvas.delete("all")
        w, h = self.width, self.height
        self.canvas.create_rectangle(0, 0, w, h, outline=BORDER_COLOR, width=2)
        # 九宫格
        for i in (1, 2):
            self.canvas.create_line(0, h * i // 3, w, h * i // 3, fill=BORDER_COLOR, dash=(4, 4))
            self.canvas.create_line(w * i // 3, 0, w * i // 3, h, fill=BORDER_COLOR, dash=(4, 4))
        # 尺寸
        self.canvas.create_text(w // 2, 25, text=f"{w} x {h}", fill=BORDER_COLOR,
                                font=("Microsoft YaHei", 10, "bold"))
        # 截图按钮
        by = h - 45
        self.canvas.create_rectangle(w // 2 - 40, by, w // 2 + 40, by + 28,
                                     fill=BORDER_COLOR, outline="")
        self.canvas.create_text(w // 2, by + 14, text="截 图", fill="white",
                                font=("Microsoft YaHei", 10, "bold"))
        # 四角手柄
        for cx, cy in [(0, 0), (w, 0), (0, h), (w, h)]:
            self.canvas.create_rectangle(cx - CORNER_SIZE, cy - CORNER_SIZE,
                                         cx + CORNER_SIZE, cy + CORNER_SIZE,
                                         fill=BORDER_COLOR, outline="")

    def _on_press(self, event):
        x, y, w, h = event.x, event.y, self.width, self.height
        # 截图按钮
        if abs(x - w // 2) < 45 and abs(y - (h - 31)) < 20:
            self.capture()
            return
        # 四角缩放
        for cx, cy, name in [(0, 0, "nw"), (w, 0, "ne"), (0, h, "sw"), (w, h, "se")]:
            if abs(x - cx) < CORNER_SIZE * 2 and abs(y - cy) < CORNER_SIZE * 2:
                self._resize = {"x": event.x_root, "y": event.y_root,
                                "w": w, "h": h, "corner": name}
                return
        # 拖拽
        self._drag = {"x": event.x_root - self.x, "y": event.y_root - self.y}

    def _on_drag(self, event):
        if self._resize:
            rd = self._resize
            dx = event.x_root - rd["x"]
            old_w, old_h, old_x, old_y = rd["w"], rd["h"], self.x, self.y
            corner = rd["corner"]

            if corner == "se":
                new_w = max(270, old_w + dx)
            elif corner == "sw":
                new_w = max(270, old_w - dx)
                self.x = event.x_root
            elif corner == "ne":
                new_w = max(270, old_w + dx)
            else:  # nw
                new_w = max(270, old_w - dx)
                self.x = event.x_root

            new_h = int(new_w * ASPECT_H / ASPECT_W)
            if corner in ("ne", "nw"):
                self.y = old_y + old_h - new_h
            self.width, self.height = new_w, new_h
            self.win.geometry(f"{new_w}x{new_h}+{self.x}+{self.y}")
            self._draw()

        elif self._drag:
            self.x = event.x_root - self._drag["x"]
            self.y = event.y_root - self._drag["y"]
            self.win.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")

    def _on_release(self, event):
        self._drag = None
        self._resize = None

    def show(self):
        self.win.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
        self._draw()
        self.win.deiconify()
        self.win.lift()
        self.active = True
        self.app.set_status("截图框已显示 — 拖拽移动 / 拖角缩放 / 点击截图")

    def hide(self):
        self.win.withdraw()
        self.active = False
        self.app.set_status("截图框已隐藏")

    def set_preset(self, name):
        size = PRESET_SIZES.get(name)
        if size:
            self.width, self.height = size
            self.win.geometry(f"{self.width}x{self.height}+{self.x}+{self.y}")
            self._draw()

    def capture(self):
        if not self.active:
            return
        x1, y1, x2, y2 = self.x, self.y, self.x + self.width, self.y + self.height
        self.win.withdraw()
        self.win.update()
        time.sleep(0.06)
        try:
            img = ImageGrab.grab(bbox=(x1, y1, x2, y2))
        except Exception as e:
            img = None
            messagebox.showerror("截图失败", str(e))
        self.win.deiconify()
        self.win.lift()
        if img:
            name = self.app.get_active_storyboard()
            self.app.add_temp(img, name)
            self._flash()

    def _flash(self):
        self.canvas.create_rectangle(0, 0, self.width, self.height,
                                     fill="#00FF41", stipple="gray50", tags="flash")
        self.win.after(150, lambda: self.canvas.delete("flash"))


# ---- Ken Burns 预览 ----
class Preview(tk.Canvas):
    def __init__(self, parent, **kw):
        kw.setdefault("bg", "#e8e8e8")
        kw.setdefault("highlightthickness", 0)
        super().__init__(parent, **kw)
        self.pil_img = None
        self._tk_img = None
        self._playing = False
        self._progress = 0.0
        self._task = None
        self.bind("<Configure>", self._on_resize)

    def set_image(self, img):
        self._playing = False
        if self._task:
            self.after_cancel(self._task)
            self._task = None
        self.pil_img = img
        self._progress = 0.0
        self._render(0.0)

    def _on_resize(self, event):
        if self.pil_img:
            self._render(self._progress)

    def _render(self, progress):
        self.delete("all")
        if not self.pil_img:
            self.create_text(200, 200, text="暂无截图\n点击下方缩略图预览",
                             fill="#999", font=("Microsoft YaHei", 12))
            return

        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw < 30:
            cw = self.master.winfo_width() - 20
        if ch < 30:
            ch = self.master.winfo_height() - 20
        cw, ch = max(cw, 200), max(ch, 200)

        scale = 1.0 + progress * 0.15
        pw, ph = self.pil_img.size
        target, img_ratio = cw / ch, pw / ph

        if img_ratio > target:
            nh = int(ch * scale)
            nw = int(nh * img_ratio)
        else:
            nw = int(cw * scale)
            nh = int(nw / img_ratio)

        resized = self.pil_img.resize((nw, nh), Image.LANCZOS)
        left = (nw - cw) // 2
        top = (nh - ch) // 2
        crop = resized.crop((left, top, left + cw, top + ch))
        self._tk_img = ImageTk.PhotoImage(crop)
        self.create_image(cw // 2, ch // 2, image=self._tk_img)

        if self._playing:
            self.create_text(cw // 2, ch - 16,
                             text=f"缩放 {scale:.2f}x", fill="#FF2442",
                             font=("Microsoft YaHei", 9))

    def play(self):
        if not self.pil_img or self._playing:
            return
        self._playing = True
        self._step(0.0)

    def _step(self, p):
        if not self._playing:
            return
        self._progress = p
        self._render(p)
        p += 0.008
        if p >= 1.0:
            p = 0.0
        self._task = self.after(33, lambda: self._step(p))

    def stop(self):
        self._playing = False
        if self._task:
            self.after_cancel(self._task)
            self._task = None
        self._progress = 0.0
        if self.pil_img:
            self._render(0.0)


# ---- 暂存图库 ----
class Gallery(tk.Frame):
    THUMB = (100, 178)

    def __init__(self, parent, app, **kw):
        super().__init__(parent, **kw)
        self.app = app
        self.items = []         # [{image, name, photo}]
        self.story_map = {}     # name → number
        self.story_order = []   # [name, ...]

        bar = tk.Frame(self, bg="#f0f0f0")
        bar.pack(fill=tk.X)
        tk.Label(bar, text="暂存截图", font=("Microsoft YaHei", 10, "bold"),
                 bg="#f0f0f0").pack(side=tk.LEFT, padx=5, pady=3)
        self.count_lbl = tk.Label(bar, text="0 张", bg="#f0f0f0", fg="#666")
        self.count_lbl.pack(side=tk.LEFT, padx=5)
        tk.Button(bar, text="全部保存", command=self.save_all,
                  bg="#FF2442", fg="white", font=("Microsoft YaHei", 9),
                  relief=tk.FLAT, padx=12).pack(side=tk.RIGHT, padx=5, pady=3)
        tk.Button(bar, text="清空", command=self.clear_all,
                  font=("Microsoft YaHei", 9), relief=tk.FLAT).pack(side=tk.RIGHT, padx=2, pady=3)

        sf = tk.Frame(self, bg="#e8e8e8")
        sf.pack(fill=tk.BOTH, expand=True)
        self.canvas = tk.Canvas(sf, bg="#e8e8e8", height=215, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        hbar = tk.Scrollbar(sf, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hbar.pack(fill=tk.X)
        self.canvas.configure(xscrollcommand=hbar.set)
        self.inner = tk.Frame(self.canvas, bg="#e8e8e8")
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>",
                        lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

    def _story_num(self, name):
        if not name:
            return "?"
        if name not in self.story_map:
            self.story_map[name] = len(self.story_order) + 1
            self.story_order.append(name)
        return str(self.story_map[name])

    def add(self, img, name):
        # 按分镜分组插入
        pos = len(self.items)
        for i in range(len(self.items) - 1, -1, -1):
            if self.items[i]["name"] == name:
                pos = i + 1
                break
        self.items.insert(pos, {"image": img, "name": name, "photo": None, "card": None})
        # 同步 app.temp_images
        self.app.temp_images.insert(pos, (img, name))
        self._rebuild()

    def _rebuild(self):
        for w in self.inner.winfo_children():
            w.destroy()
        last_name = None
        for i, item in enumerate(self.items):
            img, name = item["image"], item["name"]
            tw, th = self.THUMB
            r = img.width / img.height
            if r > tw / th:
                nw, nh = tw, int(tw / r)
            else:
                nw, nh = int(th * r), th
            thumb = img.resize((nw, nh), Image.LANCZOS)
            bg = Image.new("RGB", (tw, th), "#ccc")
            bg.paste(thumb, ((tw - nw) // 2, (th - nh) // 2))
            photo = ImageTk.PhotoImage(bg)
            item["photo"] = photo

            num = self._story_num(name)

            if name != last_name and i > 0:
                s = tk.Frame(self.inner, bg="#e8e8e8", padx=1, pady=3)
                s.pack(side=tk.LEFT)
                tk.Frame(s, bg="#FF2442", width=2, height=th).pack()
            last_name = name

            card = tk.Frame(self.inner, bg="white", padx=2, pady=2,
                            highlightbackground="#ddd", highlightthickness=1)
            card.pack(side=tk.LEFT, padx=3, pady=3)
            item["card"] = card

            tk.Label(card, text=f"分镜{num}",
                     font=("Microsoft YaHei", 8, "bold"),
                     bg="#FF2442", fg="white").pack(fill=tk.X)

            lbl = tk.Label(card, image=photo, cursor="hand2", relief=tk.FLAT, bd=0)
            lbl.image = photo
            lbl.pack()

            tk.Label(card, text=f"#{i + 1}",
                     font=("Microsoft YaHei", 7), bg="white", fg="#999").pack()

            lbl.bind("<Button-1>", lambda e, idx=i: self.app.thumb_click(idx))
            lbl.bind("<Button-3>", lambda e, idx=i: self.remove(idx))
        self._refresh_count()

    def remove(self, idx):
        if 0 <= idx < len(self.items):
            del self.items[idx]
            self.app.temp_images.pop(idx)
            self._rebuild()

    def clear_all(self):
        if not self.items:
            return
        if messagebox.askyesno("确认", f"清空全部 {len(self.items)} 张暂存截图？"):
            self.items.clear()
            self.app.temp_images.clear()
            self.story_map.clear()
            self.story_order.clear()
            for w in self.inner.winfo_children():
                w.destroy()
            self._refresh_count()

    def _refresh_count(self):
        n = len(self.items)
        self.count_lbl.config(text=f"{n} 张")

    def save_all(self):
        if not self.items:
            messagebox.showinfo("提示", "没有可保存的截图")
            return
        folder = filedialog.askdirectory(title="选择保存目录", initialdir=str(DEFAULT_SAVE_DIR))
        if not folder:
            return
        for i, item in enumerate(self.items):
            name = item["name"] or f"screenshot_{i + 1}"
            safe = re.sub(r'[\\/:*?"<>|]', "_", name)
            item["image"].save(os.path.join(folder, f"{safe}_{i + 1}.png"), "PNG")
        messagebox.showinfo("完成", f"已保存 {len(self.items)} 张截图到:\n{folder}")


# ---- 分镜面板 ----
class StoryboardPanel(tk.Frame):
    def __init__(self, parent, app, **kw):
        super().__init__(parent, **kw)
        self.app = app
        self.items = []

        hdr = tk.Frame(self, bg="#f5f5f5")
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="分镜列表", font=("Microsoft YaHei", 11, "bold"),
                 bg="#f5f5f5").pack(side=tk.LEFT, padx=8, pady=5)

        lf = tk.Frame(self, bg="white")
        lf.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        self.listbox = tk.Listbox(lf, font=("Microsoft YaHei", 9),
                                  selectmode=tk.SINGLE, relief=tk.FLAT,
                                  highlightthickness=1, highlightcolor="#FF2442")
        self.listbox.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)
        sb = tk.Scrollbar(lf, command=self.listbox.yview)
        sb.pack(fill=tk.Y, side=tk.RIGHT)
        self.listbox.config(yscrollcommand=sb.set)

        ef = tk.Frame(self, bg="#fafafa", padx=5, pady=5)
        ef.pack(fill=tk.X)
        tk.Label(ef, text="配音描述:", font=("Microsoft YaHei", 9),
                 bg="#fafafa").pack(anchor=tk.W)
        self.desc = tk.Text(ef, height=3, font=("Microsoft YaHei", 9), wrap=tk.WORD)
        self.desc.pack(fill=tk.X, pady=2)

        self.sug_lbl = tk.Label(ef, text="", font=("Microsoft YaHei", 8),
                                fg="#0078D4", bg="#fafafa", justify=tk.LEFT, wraplength=200)
        self.sug_lbl.pack(fill=tk.X, pady=2)

        bf = tk.Frame(self, bg="#f5f5f5")
        bf.pack(fill=tk.X, padx=3, pady=3)
        tk.Button(bf, text="新增", command=self.add, font=("Microsoft YaHei", 9),
                  relief=tk.FLAT, bg="#FF2442", fg="white", padx=8).pack(side=tk.LEFT, padx=2)
        tk.Button(bf, text="AI分析", command=self.analyze, font=("Microsoft YaHei", 9),
                  relief=tk.FLAT, padx=8).pack(side=tk.LEFT, padx=2)
        tk.Button(bf, text="删除", command=self.delete, font=("Microsoft YaHei", 9),
                  relief=tk.FLAT, padx=8).pack(side=tk.RIGHT, padx=2)

        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self._load()

    def _load(self):
        if DATA_FILE.exists():
            try:
                data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                self.items = data.get("storyboards", [])
            except Exception:
                self.items = []
        self._refresh()

    def _save(self):
        DATA_FILE.write_text(json.dumps({"storyboards": self.items}, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    def _refresh(self):
        self.listbox.delete(0, tk.END)
        for it in self.items:
            preview = it["description"][:30] + ("..." if len(it["description"]) > 30 else "")
            self.listbox.insert(tk.END, preview)

    def _on_select(self, event):
        sel = self.listbox.curselection()
        if not sel:
            return
        it = self.items[sel[0]]
        self.desc.delete("1.0", tk.END)
        self.desc.insert("1.0", it["description"])
        self.sug_lbl.config(text="")
        self.app.set_status(f"已选择分镜: {it['description'][:30]}")

    def add(self):
        desc = self.desc.get("1.0", tk.END).strip()
        if not desc:
            self.app.set_status("请先输入配音描述")
            return
        self.items.append({"id": str(int(time.time() * 1000)), "description": desc, "ai_suggestion": ""})
        self._save()
        self._refresh()
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(tk.END)
        self._on_select(None)
        self.app.set_status(f"已添加分镜: {desc[:30]}")

    def delete(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        it = self.items[idx]
        if messagebox.askyesno("确认", f"删除分镜「{it['description'][:30]}」？"):
            del self.items[idx]
            self._save()
            self._refresh()
            self.desc.delete("1.0", tk.END)
            self.sug_lbl.config(text="")
            self.app.set_status("分镜已删除")

    def analyze(self):
        desc = self.desc.get("1.0", tk.END).strip()
        if not desc:
            self.app.set_status("请先输入配音描述再分析")
            return
        results = analyze_description(desc)
        text = "\n".join(f"【{s}】{t}" for s, t in results)
        self.sug_lbl.config(text=text)
        sel = self.listbox.curselection()
        if sel:
            self.items[sel[0]]["ai_suggestion"] = text
            self._save()
        self.app.set_status(f"AI分析完成，匹配 {len(results)} 类来源")

    def active_desc(self):
        sel = self.listbox.curselection()
        return self.items[sel[0]]["description"] if sel else ""


# ---- 主窗口 ----
class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("截图助手 - 小红书分镜截图工具")
        self.root.geometry("1000x700")
        self.root.minsize(800, 600)

        self.temp_images = []  # [(pil_img, name), ...]

        self._build_menu()
        self._build_ui()

        self.overlay = Overlay(self)

    def _build_menu(self):
        mb = tk.Menu(self.root)
        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="显示/隐藏截图框", command=self.toggle_overlay)
        fm.add_separator()
        fm.add_command(label="退出", command=self._quit)
        mb.add_cascade(label="文件", menu=fm)
        sm = tk.Menu(mb, tearoff=0)
        for name in PRESET_SIZES:
            sm.add_command(label=name, command=lambda n=name: self.set_overlay_size(n))
        mb.add_cascade(label="截图尺寸", menu=sm)
        mb.add_command(label="帮助", command=self._help)
        self.root.config(menu=mb)

    def _build_ui(self):
        pw = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, sashwidth=3, bg="#ccc")
        pw.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

        # 左侧分镜
        left = tk.Frame(pw, width=280, bg="#f5f5f5")
        pw.add(left)
        self.storyboard = StoryboardPanel(left, self, bg="#f5f5f5")
        self.storyboard.pack(fill=tk.BOTH, expand=True)

        # 右侧预览
        right = tk.Frame(pw, bg="white")
        pw.add(right)

        ph = tk.Frame(right, bg="#f5f5f5")
        ph.pack(fill=tk.X)
        tk.Label(ph, text="Ken Burns 动画预览", font=("Microsoft YaHei", 10, "bold"),
                 bg="#f5f5f5").pack(side=tk.LEFT, padx=8, pady=5)
        self.play_btn = tk.Button(ph, text="播放", command=self.toggle_play,
                                  font=("Microsoft YaHei", 9), relief=tk.FLAT, padx=8,
                                  bg="#0078D4", fg="white")
        self.play_btn.pack(side=tk.RIGHT, padx=5, pady=3)
        tk.Button(ph, text="停止", command=self.stop_play,
                  font=("Microsoft YaHei", 9), relief=tk.FLAT, padx=8).pack(side=tk.RIGHT, padx=2, pady=3)

        pc = tk.Frame(right, bg="white")
        pc.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.preview = Preview(pc)
        self.preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 控制
        cf = tk.Frame(right, bg="#f5f5f5")
        cf.pack(fill=tk.X, padx=5, pady=5)
        self.overlay_btn = tk.Button(cf, text="打开截图框", command=self.toggle_overlay,
                                     font=("Microsoft YaHei", 11, "bold"),
                                     bg="#FF2442", fg="white", relief=tk.FLAT, padx=20, pady=6)
        self.overlay_btn.pack(side=tk.LEFT, padx=5)
        tk.Label(cf, text="快捷键: Enter/Space 截图 | Esc 隐藏",
                 font=("Microsoft YaHei", 8), fg="#999", bg="#f5f5f5").pack(side=tk.LEFT, padx=10)

        # 底部暂存
        ttk.Separator(self.root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=3)
        self.gallery = Gallery(self.root, self, height=215, bg="#e8e8e8")
        self.gallery.pack(fill=tk.X, side=tk.BOTTOM, padx=3, pady=3)

        # 状态栏
        sf = tk.Frame(self.root, bg="#e8e8e8", height=24)
        sf.pack(fill=tk.X, side=tk.BOTTOM)
        self.status_var = tk.StringVar(value="就绪 — 选择分镜 → 打开截图框 → 截图 → 筛选 → 保存")
        tk.Label(sf, textvariable=self.status_var, font=("Microsoft YaHei", 8),
                 bg="#e8e8e8", fg="#555", anchor=tk.W).pack(fill=tk.X, padx=8, pady=2)

    def set_status(self, text):
        self.status_var.set(text)

    def toggle_overlay(self):
        if self.overlay.active:
            self.overlay.hide()
            self.overlay_btn.config(text="打开截图框", bg="#FF2442")
        else:
            self.overlay.show()
            self.overlay_btn.config(text="关闭截图框", bg="#0078D4")

    def set_overlay_size(self, name):
        self.overlay.set_preset(name)
        if not self.overlay.active:
            self.overlay.show()
            self.overlay_btn.config(text="关闭截图框", bg="#0078D4")

    def get_active_storyboard(self):
        return self.storyboard.active_desc()

    def add_temp(self, img, name):
        self.gallery.add(img, name)

    def thumb_click(self, idx):
        if 0 <= idx < len(self.temp_images):
            img, name = self.temp_images[idx]
            self.preview.set_image(img)
            self.set_status(f"预览: {name or f'截图{idx+1}'} — 点击播放查看Ken Burns动画效果")

    def toggle_play(self):
        if self.preview._playing:
            self.stop_play()
        else:
            if not self.preview.pil_img:
                self.set_status("请先点击缩略图选择要预览的截图")
                return
            self.preview.play()
            self.play_btn.config(text="暂停", bg="#FF8C00")
            self.set_status("Ken Burns动画播放中")

    def stop_play(self):
        self.preview.stop()
        self.play_btn.config(text="播放", bg="#0078D4")

    def _help(self):
        messagebox.showinfo("使用帮助",
                            "📷 截图框\n"
                            "  - 拖拽移动截图框位置\n"
                            "  - 四角拖拽调整大小（自动锁定9:16）\n"
                            "  - 点击底部红色按钮 / Enter / Space 截图\n"
                            "  - Esc 隐藏截图框\n\n"
                            "📋 分镜管理\n"
                            "  - 添加配音描述后选择对应分镜\n"
                            "  - 截图自动按分镜命名归组\n"
                            "  - AI分析建议截图来源\n\n"
                            "🎬 Ken Burns预览\n"
                            "  - 点击缩略图 → 预览区显示\n"
                            "  - 播放查看缩放动画效果\n\n"
                            "💾 暂存与保存\n"
                            "  - 截图先进暂存区，右键删除废图\n"
                            "  - 筛选后全部保存")

    def _quit(self):
        if self.gallery.items:
            if not messagebox.askyesno("确认", f"还有 {len(self.gallery.items)} 张暂存截图未保存，确定退出？"):
                return
        self.overlay.win.destroy()
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.mainloop()


def main():
    App().run()


if __name__ == "__main__":
    main()
