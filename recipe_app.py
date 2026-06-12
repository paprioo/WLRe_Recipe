# recipe_app.py (最終整合版)

import webbrowser # <<<--- 在 import 區域加入這一行
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkFont  # 導入 font 模組
import sqlite3
import re
import sys  # <<<--- 導入 sys 模組
import os   # <<<--- 導入 os 模組



def get_portable_db_path(file_name):
    """
    獲取資料庫的路徑。優先使用 .exe 所在目錄，其次是開發環境的當前目錄。
    """
    # 檢查是否被 PyInstaller 打包
    if getattr(sys, 'frozen', False):
        # 如果是 .exe，則路徑是 .exe 所在的資料夾
        application_path = os.path.dirname(sys.executable)
    else:
        # 如果是開發環境，則是 .py 檔案所在的資料夾
        application_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(application_path, file_name)


# 程式啟動時，直接設定 DB_FILE 為可攜式路徑
DB_FILE = get_portable_db_path('recipes.db')
# ^^^---------------------------------------^^^

class CreateToolTip(object):
    """為 tkinter 元件創建一個 tooltip."""

    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text, event):
        "Display text in tooltip window"
        if self.tipwindow or not text:
            return

        x = event.x_root + 20
        y = event.y_root + 10

        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")

        colors = getattr(self.widget, "colors", None)
        if colors:
            bg = colors.get("panel_alt", "#1d2633")
            fg = colors.get("text", "#e4f6ff")
            border = colors.get("border", bg)
        else:
            bg, fg, border = "#1d2633", "#e4f6ff", "#1d2633"

        label = tk.Label(
            tw,
            text=text,
            justify=tk.LEFT,
            background=bg,
            foreground=fg,
            highlightbackground=border,
            highlightthickness=1,
            relief=tk.SOLID,
            borderwidth=1,
            padx=10,
            pady=8,
            wraplength=500
        )
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


# parse_stats 函式 (從 setup_database.py 複製過來)
def parse_stats(stats_str):
    stats = {'ATK': None, 'DEF': None, 'MATK': None, 'MDEF': None, 'SPD': None, 'Other': None}
    if not stats_str or '待查' in stats_str:
        stats['Other'] = stats_str if stats_str else None
        return stats
    pattern = re.compile(r'(ATK|DEF|MATK|MDEF|SPD)\s*([+-]?\d+)')
    found_stats = pattern.findall(stats_str)
    for stat_name, value in found_stats:
        stats[stat_name] = int(value)
    remaining_str = pattern.sub('', stats_str).strip()
    cleaned_other = ' '.join(remaining_str.replace(',', ' ').split())
    if cleaned_other:
        stats['Other'] = cleaned_other
    return stats


class RecipeEditor(tk.Toplevel):
    # RecipeEditor 類別的內容保持不變，因為它工作正常
    def __init__(self, parent, item_id=None):
        super().__init__(parent)
        self.parent = parent
        self.item_id = item_id
        if hasattr(parent, "colors"):
            self.configure(bg=parent.colors["bg"])
        if self.item_id:
            self.title("修改配方")
            self.load_data()
        else:
            self.title("新增配方")
            self.item_data = {}
        self.create_widgets()

    def load_data(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT species, level, name, part, formula, reference, reference_beginner, original_stats FROM recipes WHERE id = ?",
            (self.item_id,))
        data = cursor.fetchone()
        conn.close()
        if data:
            self.item_data = {
                'species': data[0], 'level': data[1], 'name': data[2], 'part': data[3],
                'formula': data[4], 'reference': data[5], 'reference_beginner': data[6], 'stats': data[7]
            }
        else:
            messagebox.showerror("錯誤", "找不到指定的物品資料！")
            self.destroy()

    def create_widgets(self):
        self.entries = {}
        fields = ['物種', '物等', '名稱', '部位', '公式', '參考配方', '參考配方(初階)', '數值']
        db_keys = ['species', 'level', 'name', 'part', 'formula', 'reference', 'reference_beginner', 'stats']
        for i, field in enumerate(fields):
            label = ttk.Label(self, text=f"{field}:")
            label.grid(row=i, column=0, padx=10, pady=5, sticky='w')
            entry = ttk.Entry(self, width=60)
            entry.grid(row=i, column=1, padx=10, pady=5, sticky='ew')
            if self.item_id and db_keys[i] in self.item_data:
                entry.insert(0, self.item_data.get(db_keys[i], ''))
            self.entries[db_keys[i]] = entry
        save_button = ttk.Button(self, text="儲存", command=self.save)
        save_button.grid(row=len(fields), column=0, columnspan=2, pady=10)

    def save(self):
        data_to_save = {key: entry.get().strip() for key, entry in self.entries.items()}
        if not data_to_save['name'] or not data_to_save['species']:
            messagebox.showwarning("輸入錯誤", "「名稱」和「物種」為必填欄位！")
            return

        level_str = data_to_save['level']
        if level_str and not level_str.isdigit():
            messagebox.showwarning("輸入錯誤", "「物等」必須是數字（或留空）！")
            self.entries['level'].focus_set()
            return
        level_value = int(level_str) if level_str else None

        stats_str = data_to_save['stats']
        parsed_stats = parse_stats(stats_str)

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        try:
            # vvv--- 這是核心修正：確保 data_tuple 有 14 個元素 ---vvv
            data_tuple = (
                data_to_save['species'],
                level_value,
                data_to_save['name'],
                data_to_save['part'],
                data_to_save['formula'],
                data_to_save['reference'],
                data_to_save['reference_beginner'],
                stats_str,  # original_stats
                parsed_stats['ATK'],
                parsed_stats['DEF'],
                parsed_stats['MATK'],
                parsed_stats['MDEF'],
                parsed_stats['SPD'],
                parsed_stats['Other']
            )

            if self.item_id:
                # UPDATE 語句，SET 部分有 14 個欄位，WHERE 部分有 1 個 (id)
                # 總共需要 15 個參數
                update_query = """
                    UPDATE recipes 
                    SET species=?, level=?, name=?, part=?, formula=?, reference=?, 
                        reference_beginner=?, original_stats=?, ATK=?, DEF=?, 
                        MATK=?, MDEF=?, SPD=?, Other=?
                    WHERE id=?
                """
                # 將 item_id 加入到元組的末尾
                cursor.execute(update_query, (*data_tuple, self.item_id))
            else:
                # INSERT 語句，VALUES 部分有 14 個佔位符
                insert_query = """
                    INSERT INTO recipes (species, level, name, part, formula, reference, 
                                         reference_beginner, original_stats, ATK, DEF, 
                                         MATK, MDEF, SPD, Other)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                cursor.execute(insert_query, data_tuple)

            # ^^^----------------------------------------------------^^^

            conn.commit()
            messagebox.showinfo("成功", "資料已成功儲存！")
            self.parent.refresh_all()
            self.destroy()

        except sqlite3.IntegrityError:
            messagebox.showerror("錯誤", f"物品名稱 '{data_to_save['name']}' 已存在，無法重複新增。")
        except Exception as e:
            messagebox.showerror("資料庫錯誤", f"儲存失敗：{e}")
        finally:
            conn.close()


class BatchRecipeImporter(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("批量新增配方")
        self.geometry("1200x640")
        self.minsize(900, 520)
        if hasattr(parent, "colors"):
            self.configure(bg=parent.colors["bg"])
        self.columns = ['物種', '物等', '名稱', '部位', '公式', '參考配方', '參考配方(初階)', '數值']
        self.db_keys = ['species', 'level', 'name', 'part', 'formula', 'reference', 'reference_beginner', 'stats']
        self._edit_entry = None
        self.create_widgets()

    def create_widgets(self):
        colors = getattr(self.parent, "colors", None)

        intro = ttk.Label(
            self,
            text="請從 Excel 選取整個範圍（含8欄）複製，點一下表格任一格再按 Ctrl+V 貼上。"
                 "雙擊儲存格可直接修改內容，可用「新增列／刪除選取列」調整行數。",
            wraplength=1150
        )
        intro.pack(fill='x', padx=16, pady=(16, 8))

        button_frame = ttk.Frame(self)
        button_frame.pack(side='bottom', fill='x', padx=16, pady=(0, 16))

        table_frame = ttk.Frame(self)
        table_frame.pack(expand=True, fill='both', padx=16, pady=(0, 10))

        # 用 Treeview 模擬 Excel 表格：標題列為中文欄位名稱
        self.tree = ttk.Treeview(
            table_frame,
            columns=self.db_keys,
            show='headings',
            height=18,
            selectmode='extended'
        )
        col_widths = {
            'species': 90, 'level': 60, 'name': 140, 'part': 80,
            'formula': 180, 'reference': 180, 'reference_beginner': 180, 'stats': 160
        }
        for db_key, display_name in zip(self.db_keys, self.columns):
            self.tree.heading(db_key, text=display_name)
            self.tree.column(db_key, width=col_widths.get(db_key, 120), anchor='w', stretch=True)

        y_scroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        y_scroll.grid(row=0, column=1, sticky='ns')
        x_scroll.grid(row=1, column=0, sticky='ew')
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        if colors:
            self.tree.tag_configure('evenrow', background=colors.get("row_even"))
            self.tree.tag_configure('oddrow', background=colors.get("row_odd"))

        # 初始給一些空白列，方便直接貼上或手動輸入
        for _ in range(20):
            self._append_empty_row()

        # 雙擊儲存格 -> 編輯；Ctrl+V -> 貼上 Excel 內容
        self.tree.bind('<Double-1>', self.on_cell_double_click)
        self.tree.bind('<Control-v>', self.on_paste)
        self.tree.bind('<Control-V>', self.on_paste)

        ttk.Button(button_frame, text="從剪貼簿貼上", command=self.on_paste).pack(side='left')
        ttk.Button(button_frame, text="新增一列", command=lambda: self._append_empty_row(select=True)).pack(side='left', padx=8)
        ttk.Button(button_frame, text="刪除選取列", command=self.delete_selected_rows).pack(side='left')
        ttk.Button(button_frame, text="清空全部", command=self.clear_all_rows).pack(side='left', padx=8)
        ttk.Button(button_frame, text="批量新增", command=self.import_recipes, style='Accent.TButton').pack(side='right')

    # ------------------------------------------------------------------
    # 表格列的基本操作
    # ------------------------------------------------------------------
    def _retag_rows(self):
        for index, item in enumerate(self.tree.get_children()):
            tag = 'evenrow' if index % 2 == 0 else 'oddrow'
            self.tree.item(item, tags=(tag,))

    def _append_empty_row(self, select=False):
        item = self.tree.insert('', 'end', values=[''] * len(self.db_keys))
        self._retag_rows()
        if select:
            self.tree.selection_set(item)
            self.tree.see(item)
        return item

    def delete_selected_rows(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("提示", "請先選取要刪除的列。")
            return
        for item in selected:
            self.tree.delete(item)
        self._retag_rows()

    def clear_all_rows(self):
        if not messagebox.askyesno("確認", "確定要清空表格中的所有內容嗎？"):
            return
        self.tree.delete(*self.tree.get_children())
        for _ in range(20):
            self._append_empty_row()

    # ------------------------------------------------------------------
    # 儲存格編輯（雙擊）
    # ------------------------------------------------------------------
    def on_cell_double_click(self, event):
        if self._edit_entry is not None:
            self._finish_edit()

        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return
        row_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)  # 例如 '#1'
        if not row_id or not col_id:
            return
        col_index = int(col_id[1:]) - 1
        if col_index < 0 or col_index >= len(self.db_keys):
            return
        db_key = self.db_keys[col_index]

        x, y, width, height = self.tree.bbox(row_id, col_id)
        current_value = self.tree.set(row_id, db_key)

        entry = ttk.Entry(self.tree)
        entry.place(x=x, y=y, width=width, height=height)
        entry.insert(0, current_value)
        entry.focus_set()
        entry.select_range(0, 'end')

        self._edit_entry = entry
        self._edit_target = (row_id, db_key)

        entry.bind('<Return>', lambda e: self._finish_edit())
        entry.bind('<KP_Enter>', lambda e: self._finish_edit())
        entry.bind('<Escape>', lambda e: self._cancel_edit())
        entry.bind('<FocusOut>', lambda e: self._finish_edit())

    def _finish_edit(self):
        if self._edit_entry is None:
            return
        row_id, db_key = self._edit_target
        value = self._edit_entry.get()
        if self.tree.exists(row_id):
            self.tree.set(row_id, db_key, value.strip())
        self._edit_entry.destroy()
        self._edit_entry = None
        self._edit_target = None

    def _cancel_edit(self):
        if self._edit_entry is None:
            return
        self._edit_entry.destroy()
        self._edit_entry = None
        self._edit_target = None

    # ------------------------------------------------------------------
    # 從 Excel 貼上
    # ------------------------------------------------------------------
    def on_paste(self, event=None):
        try:
            clipboard_text = self.clipboard_get()
        except tk.TclError:
            messagebox.showwarning("貼上失敗", "剪貼簿目前沒有可貼上的文字。")
            return "break"

        rows_text = clipboard_text.replace('\r\n', '\n').replace('\r', '\n').strip('\n')
        if not rows_text:
            return "break"
        pasted_rows = rows_text.split('\n')

        # 如果第一行剛好是標題列（與顯示欄位名稱相同），就跳過
        first_cells = [c.strip() for c in pasted_rows[0].split('\t')]
        if first_cells[:len(self.columns)] == self.columns:
            pasted_rows = pasted_rows[1:]
        if not pasted_rows:
            return "break"

        # 從目前選取/聚焦的列開始覆蓋；若沒有選取，從第一列開始
        children = self.tree.get_children()
        focused = self.tree.focus()
        if focused and focused in children:
            start_index = children.index(focused)
        else:
            start_index = 0

        for offset, line in enumerate(pasted_rows):
            cells = [cell.strip() for cell in line.split('\t')]
            target_index = start_index + offset
            children = self.tree.get_children()
            if target_index < len(children):
                item = children[target_index]
            else:
                item = self._append_empty_row()
            for col_index, db_key in enumerate(self.db_keys):
                value = cells[col_index] if col_index < len(cells) else ''
                self.tree.set(item, db_key, value)

        self._retag_rows()
        return "break"

    # ------------------------------------------------------------------
    # 匯入前的整理與驗證
    # ------------------------------------------------------------------
    def parse_pasted_rows(self):
        rows = []
        errors = []
        for line_number, item in enumerate(self.tree.get_children(), start=1):
            values = self.tree.item(item).get('values', [])
            cells = [str(v).strip() if v is not None else '' for v in values]
            if len(cells) < len(self.db_keys):
                cells += [''] * (len(self.db_keys) - len(cells))

            # 整列都是空白 -> 視為佔位空列，直接跳過
            if not any(cells):
                continue

            row = dict(zip(self.db_keys, cells))
            if not row['species'] or not row['name']:
                errors.append(f"第 {line_number} 列缺少必填欄位：物種或名稱。")
                continue
            if row['level'] and not row['level'].isdigit():
                errors.append(f"第 {line_number} 列「物等」必須是數字：{row['level']}")
                continue
            rows.append(row)

        return rows, errors

    def build_data_tuple(self, row):
        stats_str = row['stats']
        parsed_stats = parse_stats(stats_str)
        return (
            row['species'],
            int(row['level']) if row['level'] else None,
            row['name'],
            row['part'],
            row['formula'],
            row['reference'],
            row['reference_beginner'],
            stats_str,
            parsed_stats['ATK'],
            parsed_stats['DEF'],
            parsed_stats['MATK'],
            parsed_stats['MDEF'],
            parsed_stats['SPD'],
            parsed_stats['Other']
        )

    def import_recipes(self):
        rows, errors = self.parse_pasted_rows()
        if errors:
            messagebox.showwarning("資料格式需要調整", "\n".join(errors[:10]))
            return
        if not rows:
            messagebox.showwarning("沒有資料", "沒有可匯入的資料。")
            return

        insert_query = """
            INSERT INTO recipes (species, level, name, part, formula, reference,
                                 reference_beginner, original_stats, ATK, DEF,
                                 MATK, MDEF, SPD, Other)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        inserted_count = 0
        skipped_names = []
        try:
            for row in rows:
                try:
                    cursor.execute(insert_query, self.build_data_tuple(row))
                    inserted_count += 1
                except sqlite3.IntegrityError:
                    skipped_names.append(row['name'])
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("資料庫錯誤", f"批量新增失敗：{e}")
            return
        finally:
            conn.close()

        message = f"成功新增 {inserted_count} 筆資料。"
        if skipped_names:
            message += f"\n略過 {len(skipped_names)} 筆重複名稱：{', '.join(skipped_names[:10])}"
            if len(skipped_names) > 10:
                message += "..."
        messagebox.showinfo("批量新增完成", message)
        self.parent.refresh_all()
        self.destroy()


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("飄流幻境煉金查詢器")
        self.geometry("1600x900")
        self.sort_by = None
        self.sort_descending = False
        self.minsize(1180, 720)

        self.theme_presets = {
            "深夜藍": {
                "bg": "#0b1220",
                "panel": "#111a2b",
                "panel_alt": "#162235",
                "surface": "#1a2738",
                "surface_alt": "#223149",
                "accent": "#67c7ff",
                "accent_dark": "#2e86c1",
                "accent_soft": "#8ad8ff",
                "text": "#eef6ff",
                "muted": "#b8c7d9",
                "border": "#2b3a52",
                "row_odd": "#152031",
                "row_even": "#1a2638",
                "row_selected": "#2b5d87",
                "warning": "#ffcf5c",
            },
            "石墨灰": {
                "bg": "#111316",
                "panel": "#171b20",
                "panel_alt": "#20252c",
                "surface": "#232931",
                "surface_alt": "#2b323c",
                "accent": "#77c9ff",
                "accent_dark": "#4f9fcf",
                "accent_soft": "#b4e7ff",
                "text": "#f0f4f8",
                "muted": "#b2bbc6",
                "border": "#363e49",
                "row_odd": "#1a1f26",
                "row_even": "#20262f",
                "row_selected": "#355f7f",
                "warning": "#ffd36b",
            },
            "暗夜紫": {
                "bg": "#13101d",
                "panel": "#1c1730",
                "panel_alt": "#251f3d",
                "surface": "#2a2342",
                "surface_alt": "#332b50",
                "accent": "#b48cff",
                "accent_dark": "#7c5cd6",
                "accent_soft": "#d3bbff",
                "text": "#f3eeff",
                "muted": "#c3b8de",
                "border": "#3b3258",
                "row_odd": "#1d1832",
                "row_even": "#241e3a",
                "row_selected": "#5d4a99",
                "warning": "#ffcf8a",
            },
            "森林綠": {
                "bg": "#0c1712",
                "panel": "#13241c",
                "panel_alt": "#1a2f25",
                "surface": "#1f3a2e",
                "surface_alt": "#27483a",
                "accent": "#6fe0a8",
                "accent_dark": "#3aa777",
                "accent_soft": "#a8f0cc",
                "text": "#eafff3",
                "muted": "#b6d6c5",
                "border": "#2e4a3c",
                "row_odd": "#152a21",
                "row_even": "#1b352a",
                "row_selected": "#3b6e57",
                "warning": "#ffd97a",
            },
            "暖木棕": {
                "bg": "#1c1410",
                "panel": "#271c16",
                "panel_alt": "#32241b",
                "surface": "#3a2a1f",
                "surface_alt": "#473326",
                "accent": "#f0b873",
                "accent_dark": "#c4863f",
                "accent_soft": "#ffd6a3",
                "text": "#fdf2e7",
                "muted": "#d8c0aa",
                "border": "#4d3a2c",
                "row_odd": "#241a13",
                "row_even": "#2e2118",
                "row_selected": "#7a5839",
                "warning": "#ffe08a",
            },
            "明亮白": {
                "bg": "#f4f4f6",
                "panel": "#ffffff",
                "panel_alt": "#ececef",
                "surface": "#ffffff",
                "surface_alt": "#e9e9ec",
                "accent": "#5b8def",
                "accent_dark": "#3f6fd1",
                "accent_soft": "#8fb4ff",
                "text": "#2b2d33",
                "muted": "#7a7d87",
                "border": "#d6d6db",
                "row_odd": "#ffffff",
                "row_even": "#f1f1f4",
                "row_selected": "#cfe0ff",
                "warning": "#e0a32f",
            },
            "淡粉紅": {
                "bg": "#fdf2f4",
                "panel": "#ffffff",
                "panel_alt": "#fbe6ea",
                "surface": "#ffffff",
                "surface_alt": "#fbe6ea",
                "accent": "#ec7fa0",
                "accent_dark": "#d85f85",
                "accent_soft": "#ffb3c6",
                "text": "#3a2b30",
                "muted": "#9b7e86",
                "border": "#f3cdd6",
                "row_odd": "#ffffff",
                "row_even": "#fdeef1",
                "row_selected": "#ffd3df",
                "warning": "#e0a32f",
            },
        }
        self.theme_name = tk.StringVar(value="石墨灰")
        self.colors = self.theme_presets[self.theme_name.get()]

        # vvv--- 新增字體管理相關 ---vvv
        # 創建一個 Style 物件
        self.style = ttk.Style(self)
        self.style.theme_use('clam')

        # 定義一個可用的字體列表 (優先選擇支援中文的)
        self.available_fonts = ["Microsoft YaHei UI", "Microsoft JhengHei UI", "SimHei", "Arial", "Calibri"]
        # 過濾出系統中實際存在的字體
        self.system_fonts = [f for f in self.available_fonts if f in tkFont.families()]
        if not self.system_fonts: self.system_fonts = list(tkFont.families())  # 如果預設的都不在，就用系統所有字體

        self.font_family = tk.StringVar(value=self.system_fonts[0])
        self.font_size = tk.IntVar(value=10)
        # ^^^-----------------------^^^
        self.configure(bg=self.colors["bg"])
        self.setup_modern_theme(self.theme_name.get())

        self.column_map = {
            'ID': 'id', '物種': 'species', '物等': 'level', '名稱': 'name', '部位': 'part',
            'ATK': 'atk', 'DEF': 'def', 'MATK': 'matk', 'MDEF': 'mdef', 'SPD': 'spd',
            '其他': 'other', '公式': 'formula', '參考配方': 'reference', '參考配方(初階)': 'reference_beginner'
        }
        self.columns_order = list(self.column_map.keys())
        self.filters = {}

        self.create_widgets()
        self.populate_filter_options()
        self.apply_filters()

        self.tooltip = CreateToolTip(self)
        self._tooltip_after_id = None  # 用於存放 after 計時器的 ID
        self._last_tooltip_cell = None  # 用於記錄上一個觸發 tooltip 的儲存格

    # ^^^-----------------------^^^
    def setup_modern_theme(self, theme_name=None):
        """套用可切換的現代化深色模板。"""
        if theme_name is None:
            theme_name = self.theme_name.get()
        self.theme_name.set(theme_name)
        self.colors = self.theme_presets.get(theme_name, self.theme_presets["深夜藍"])
        self.option_add("*Font", (self.font_family.get(), self.font_size.get()))
        self.option_add("*TCombobox*Listbox.background", self.colors["panel"])
        self.option_add("*TCombobox*Listbox.foreground", self.colors["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", self.colors["accent_dark"])
        self.option_add("*TCombobox*Listbox.selectForeground", self.colors["text"])

        self.style.configure('.', background=self.colors["bg"], foreground=self.colors["text"], fieldbackground=self.colors["surface"], bordercolor=self.colors["border"])
        self.style.configure('TFrame', background=self.colors["bg"])
        self.style.configure('Card.TFrame', background=self.colors["panel"], relief='flat')
        self.style.configure('TLabelframe', background=self.colors["panel"], foreground=self.colors["accent_soft"], borderwidth=1, relief='solid', padding=10)
        self.style.configure('TLabelframe.Label', background=self.colors["panel"], foreground=self.colors["accent_soft"], font=(self.font_family.get(), self.font_size.get(), 'bold'))
        self.style.configure('TLabel', background=self.colors["bg"], foreground=self.colors["text"])
        self.style.configure('Card.TLabel', background=self.colors["panel"], foreground=self.colors["text"])
        self.style.configure('TButton', padding=(14, 9), background=self.colors["surface"], foreground=self.colors["text"], borderwidth=0, focusthickness=0, relief='flat')
        self.style.map('TButton',
                       background=[('active', self.colors["accent_dark"]), ('pressed', self.colors["accent"])],
                       foreground=[('disabled', self.colors["muted"])])
        self.style.configure('Accent.TButton', padding=(14, 9), background=self.colors["accent_dark"], foreground=self.colors["text"], borderwidth=0, relief='flat')
        self.style.map('Accent.TButton',
                       background=[('active', self.colors["accent"]), ('pressed', self.colors["accent_soft"])])
        self.style.configure('TEntry', fieldbackground=self.colors["surface"], background=self.colors["surface"], foreground=self.colors["text"], insertcolor=self.colors["text"], bordercolor=self.colors["border"], lightcolor=self.colors["border"], darkcolor=self.colors["border"], padding=8)
        self.style.configure('Compact.TEntry', fieldbackground=self.colors["surface"], background=self.colors["surface"], foreground=self.colors["text"], insertcolor=self.colors["text"], bordercolor=self.colors["border"], lightcolor=self.colors["border"], darkcolor=self.colors["border"], padding=4)
        self.style.configure('TCombobox', fieldbackground=self.colors["surface"], background=self.colors["surface"], foreground=self.colors["text"], arrowcolor=self.colors["accent"], padding=8)
        self.style.map('TCombobox',
                       fieldbackground=[('readonly', self.colors["surface"]), ('focus', self.colors["surface_alt"])],
                       foreground=[('readonly', self.colors["text"])])
        self.style.configure('TRadiobutton', background=self.colors["panel"], foreground=self.colors["text"], padding=4)
        self.style.map('TRadiobutton', foreground=[('active', self.colors["accent_soft"])])
        self.style.configure('TCheckbutton', background=self.colors["panel"], foreground=self.colors["text"], padding=4)
        self.style.map('TCheckbutton', foreground=[('active', self.colors["accent_soft"])])
        self.style.configure('Treeview',
                             background=self.colors["surface"],
                             fieldbackground=self.colors["surface"],
                             foreground=self.colors["text"],
                             rowheight=34,
                             bordercolor=self.colors["border"],
                             borderwidth=0)
        self.style.configure('Treeview.Heading',
                             background=self.colors["panel_alt"],
                             foreground=self.colors["accent_soft"],
                             relief='flat',
                             padding=(14, 10),
                             font=(self.font_family.get(), self.font_size.get(), 'bold'))
        self.style.map('Treeview.Heading',
                       background=[('active', self.colors["accent_dark"])],
                       foreground=[('active', self.colors["text"])])
        self.style.map('Treeview',
                       background=[('selected', self.colors["row_selected"])],
                       foreground=[('selected', self.colors["text"])])
        self.configure(bg=self.colors["bg"])
        if hasattr(self, "species_listbox"):
            self.species_listbox.configure(
                bg=self.colors["surface"],
                fg=self.colors["text"],
                selectbackground=self.colors["accent_dark"],
                selectforeground=self.colors["text"],
                highlightbackground=self.colors["border"],
                highlightcolor=self.colors["accent"],
            )
        if hasattr(self, "source_link_labels"):
            for label in self.source_link_labels:
                label.configure(bg=self.colors["panel"], fg=self.colors["accent_soft"])
        if hasattr(self, "tree"):
            self.tree.tag_configure('evenrow', background=self.colors["row_even"])
            self.tree.tag_configure('oddrow', background=self.colors["row_odd"])
        if hasattr(self, "_themed_panel_frames"):
            for frame in self._themed_panel_frames:
                frame.configure(bg=self.colors["panel"])
                # 只有最外層的卡片 (有 highlightbackground) 才需要更新外框色
                if "highlightbackground" in frame.keys():
                    frame.configure(highlightbackground=self.colors["border"])

    def change_theme(self, event=None):
        """切換模板並重新套用樣式。"""
        self.setup_modern_theme(self.theme_combo.get())

    def create_widgets(self):
        main_pane = ttk.PanedWindow(self, orient='horizontal')
        main_pane.pack(expand=True, fill='both', padx=18, pady=18)

        # --- 左側 ---
        left_frame = ttk.Frame(main_pane, style='Card.TFrame')  # 我們不再需要 Labelframe
        main_pane.add(left_frame, weight=0)
        left_frame.configure(width=280)

        # --- 左側上方：物種列表 ---
        species_frame = ttk.Labelframe(left_frame, text="物種列表")
        species_frame.pack(expand=True, fill='both', padx=12, pady=(12, 10))
        self.species_listbox = tk.Listbox(
            species_frame,
            exportselection=False,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            selectbackground=self.colors["accent_dark"],
            selectforeground=self.colors["text"],
            highlightthickness=1,
            highlightbackground=self.colors["border"],
            highlightcolor=self.colors["accent"],
            relief='flat',
            borderwidth=0,
            activestyle='none'
        )
        self.species_listbox.pack(expand=True, fill='both', padx=10, pady=10)
        self.species_listbox.bind('<<ListboxSelect>>', lambda event: self.apply_filters())

        # vvv--- 新增這個區塊：左側下方：資料來源 ---vvv
        source_frame = ttk.Labelframe(left_frame, text="資料參考來源")
        source_frame.pack(side='bottom', fill='x', padx=12, pady=(0, 12))

        # 定義超連結的文字和對應的網址
        links = {
            "巴哈姆特鍊金百科(tonytony7310)": "https://forum.gamer.com.tw/G1.php?bsn=8897&parent=5247",
            "巴哈姆特[星耀]屬爬等表(nrmk132475)": "https://forum.gamer.com.tw/C.php?bsn=82442&snA=139&tnum=5",
            "巴哈姆特星飄－煉金百科(nrmk132475)": "https://forum.gamer.com.tw/Co.php?bsn=82442&sn=446",
            "裝備合成表(aska2500)": "https://nextjs-github-vercel.vercel.app/"


        }

        # 創建超連結標籤
        self.source_link_labels = []
        for text, url in links.items():
            link_label = tk.Label(source_frame, text=text, fg=self.colors["accent_soft"], bg=self.colors["panel"], cursor="hand2")
            link_label.pack(anchor='w', padx=10, pady=5)
            # 使用 lambda 來確保每個標籤都綁定到正確的 URL
            link_label.bind("<Button-1>", lambda event, link=url: self.open_url(link))
            self.source_link_labels.append(link_label)
        # ^^^-------------------------------------------------^^^

        # 右側
        right_container = ttk.Frame(main_pane)
        main_pane.add(right_container, weight=1)
        filter_area = ttk.Frame(right_container);
        filter_area.pack(side='top', fill='x', pady=(0, 10))

        # 篩選器元件的創建...
        kw_row, kw_content = self.build_filter_card(filter_area, "關鍵字")
        self.filters['keyword'] = ttk.Entry(kw_content, style='Compact.TEntry')
        self.filters['keyword'].pack(side='left', expand=True, fill='x')
        # vvv--- 新增這一行事件綁定 ---vvv
        # 當使用者在 Entry 中按下 Enter 鍵 (<Return>) 時，呼叫 apply_filters 方法
        self.filters['keyword'].bind('<Return>', lambda event: self.apply_filters())
        # ^^^--------------------------^^^

        part_row, part_content = self.build_filter_card(filter_area, "部位")
        self.part_frame = ttk.Frame(part_content, style='Card.TFrame')
        self.part_frame.pack(side='left', expand=True, fill='x')
        self.filters['parts'] = {}

        stat_count_row, stat_count_content = self.build_filter_card(filter_area, "屬性數量")
        stat_count_frame = ttk.Frame(stat_count_content, style='Card.TFrame')
        stat_count_frame.pack(side='left', expand=True, fill='x')
        self.filters['stat_count'] = tk.StringVar(value="全部")
        for option in ['全部', '單屬性', '多屬性', '無屬性']:
            rb = ttk.Radiobutton(stat_count_frame, text=option, variable=self.filters['stat_count'], value=option).pack(
                side='left', padx=5)

        stats_row, stats_content = self.build_filter_card(filter_area, "數值範圍")
        stats_frame = ttk.Frame(stats_content, style='Card.TFrame')
        stats_frame.pack(side='left', expand=True, fill='x')
        for stat in ['ATK', 'DEF', 'MATK', 'MDEF', 'SPD']:
            stat_group = ttk.Frame(stats_frame, style='Card.TFrame');
            stat_group.pack(side='left', padx=(0, 15));
            ttk.Label(stat_group, text=f"{stat}").pack()
            entry_group = ttk.Frame(stat_group, style='Card.TFrame');
            entry_group.pack()
            self.filters[f'{stat}_min'] = ttk.Entry(entry_group, width=5, style='Compact.TEntry');
            self.filters[f'{stat}_min'].pack(side='left')
            ttk.Label(entry_group, text="-").pack(side='left', padx=2)
            self.filters[f'{stat}_max'] = ttk.Entry(entry_group, width=5, style='Compact.TEntry');
            self.filters[f'{stat}_max'].pack(side='left')

        # --- 第五行：按鈕 & 字體設定 ---
        control_card, control_frame = self.build_filter_card(filter_area, "控制")
        control_card.pack_configure(pady=(4, 0))

        # 按鈕
        ttk.Button(control_frame, text="應用篩選", command=self.apply_filters, style='Accent.TButton').pack(side='left')
        ttk.Button(control_frame, text="重設篩選", command=self.reset_filters).pack(side='left', padx=10)

        # vvv--- 新增字體設定區 ---vvv
        font_control_frame = ttk.Frame(control_frame, style='Card.TFrame')
        font_control_frame.pack(side='left', padx=24)

        ttk.Label(font_control_frame, text="字體:").pack(side='left')
        self.font_family_combo = ttk.Combobox(font_control_frame, state="readonly", width=15)
        self.font_family_combo.pack(side='left', padx=(0, 10))

        ttk.Label(font_control_frame, text="大小:").pack(side='left')
        self.font_size_combo = ttk.Combobox(font_control_frame, state="readonly", width=5)
        self.font_size_combo.pack(side='left')

        # 綁定事件
        self.font_family_combo.bind("<<ComboboxSelected>>", self.update_font)
        self.font_size_combo.bind("<<ComboboxSelected>>", self.update_font)
        # ^^^-----------------------^^^

        # 新增/修改/刪除按鈕移到最右邊
        ttk.Button(control_frame, text="批量新增", command=self.batch_add_recipes, style='Accent.TButton').pack(side='right', padx=8)
        ttk.Button(control_frame, text="修改選定配方", command=self.modify_recipe).pack(side='right', padx=8)
        ttk.Button(control_frame, text="刪除選定配方", command=self.delete_recipe).pack(side='right', padx=8)

        theme_frame = ttk.Frame(control_frame, style='Card.TFrame')
        theme_frame.pack(side='left', padx=18)
        ttk.Label(theme_frame, text="模板:").pack(side='left')
        self.theme_combo = ttk.Combobox(theme_frame, state="readonly", width=10)
        self.theme_combo['values'] = list(self.theme_presets.keys())
        self.theme_combo.set(self.theme_name.get())
        self.theme_combo.pack(side='left', padx=(6, 0))
        self.theme_combo.bind("<<ComboboxSelected>>", self.change_theme)

        tree_frame = ttk.Frame(right_container);
        tree_frame.pack(expand=True, fill='both', pady=(8, 0))
        self.tree = ttk.Treeview(tree_frame, columns=self.columns_order, show='headings')
        # ... (後續 Treeview 設定保持不變) ...
        for col in self.columns_order: self.tree.heading(col, text=col)
        self.tree.column('ID', width=40, anchor='center');
        self.tree.column('物種', width=50);
        self.tree.column('物等', width=40, anchor='center');
        self.tree.column('名稱', width=120);
        self.tree.column('部位', width=60);
        self.tree.column('ATK', width=50, anchor='center');
        self.tree.column('DEF', width=50, anchor='center');
        self.tree.column('MATK', width=50, anchor='center');
        self.tree.column('MDEF', width=50, anchor='center');
        self.tree.column('SPD', width=50, anchor='center');
        self.tree.column('其他', width=100);
        self.tree.column('公式', width=150);
        self.tree.column('參考配方', width=250);
        self.tree.column('參考配方(初階)', width=150)
        self.tree.bind('<Button-1>', self.on_header_click);
        self.tree.bind('<Double-1>', self.on_header_double_click)
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview);
        hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.tree.grid(row=0, column=0, sticky='nsew');
        vsb.grid(row=0, column=1, sticky='ns');
        hsb.grid(row=1, column=0, sticky='ew')
        tree_frame.grid_rowconfigure(0, weight=1);
        tree_frame.grid_columnconfigure(0, weight=1)
        # 綁定滑鼠移動事件
        self.tree.bind('<Motion>', self.on_tree_motion)
        self.tree.tag_configure('evenrow', background=self.colors["row_even"])
        self.tree.tag_configure('oddrow', background=self.colors["row_odd"])

    def build_filter_card(self, parent, title):
        """建立一個卡片式篩選列。"""
        card = tk.Frame(
            parent,
            bg=self.colors["panel"],
            highlightbackground=self.colors["border"],
            highlightthickness=1,
            bd=0
        )
        card.pack(fill='x', pady=2)

        title_label = ttk.Label(card, text=title, style='Card.TLabel', width=10)
        title_label.pack(side='left', padx=(14, 10), pady=6, anchor='n')

        separator = ttk.Separator(card, orient='vertical')
        separator.pack(side='left', fill='y', pady=4)

        content = tk.Frame(card, bg=self.colors["panel"])
        content.pack(side='left', expand=True, fill='x', padx=12, pady=4)

        if not hasattr(self, "_themed_panel_frames"):
            self._themed_panel_frames = []
        self._themed_panel_frames.extend([card, content])

        return card, content

    def populate_filter_options(self):
        """從資料庫讀取選項，填充左側列表和頂部篩選器"""
        # --- 填充物種列表 ---
        # 記住當前選擇，以便在列表刷新後恢復
        current_selection = "全部"
        if self.species_listbox.curselection():
            current_selection = self.species_listbox.get(self.species_listbox.curselection()[0])

        self.species_listbox.delete(0, 'end')
        self.species_listbox.insert('end', "全部")
        species_data = self.run_query(
            "SELECT DISTINCT species FROM recipes WHERE species IS NOT NULL AND species != '' ORDER BY species")
        for row in species_data: self.species_listbox.insert('end', row['species'])

        # 嘗試恢復之前的選擇
        try:
            idx = self.species_listbox.get(0, 'end').index(current_selection)
            self.species_listbox.selection_set(idx)
        except ValueError:
            self.species_listbox.selection_set(0)  # 如果找不到了，就選'全部'

        # --- 填充部位多選框 ---
        for widget in self.part_frame.winfo_children(): widget.destroy()
        self.filters['parts'] = {}
        part_data = self.run_query(
            "SELECT DISTINCT part FROM recipes WHERE part IS NOT NULL AND part != '' ORDER BY part")
        for row in part_data:
            part_name = row['part']
            var = tk.BooleanVar(value=False)
            cb = ttk.Checkbutton(self.part_frame, text=part_name, variable=var)
            cb.pack(side='left', padx=3)
            self.filters['parts'][part_name] = var

        # vvv--- 新增填充字體選項的程式碼 ---vvv
        self.font_family_combo['values'] = self.system_fonts
        self.font_family_combo.set(self.font_family.get())

        self.font_size_combo['values'] = [8, 9, 10, 11, 12, 14, 16, 18]
        self.font_size_combo.set(self.font_size.get())
        # ^^^------------------------------^^^

    def apply_filters(self):
        # apply_filters 的邏輯是正確的，保持不變
        base_query = "SELECT * FROM recipes"
        stat_count_logic = "(CASE WHEN ATK NOT NULL AND ATK!=0 THEN 1 ELSE 0 END + CASE WHEN DEF NOT NULL AND DEF!=0 THEN 1 ELSE 0 END + CASE WHEN MATK NOT NULL AND MATK!=0 THEN 1 ELSE 0 END + CASE WHEN MDEF NOT NULL AND MDEF!=0 THEN 1 ELSE 0 END + CASE WHEN SPD NOT NULL AND SPD!=0 THEN 1 ELSE 0 END)"
        positive_stat_count_logic = "(CASE WHEN ATK > 0 THEN 1 ELSE 0 END + CASE WHEN DEF > 0 THEN 1 ELSE 0 END + CASE WHEN MATK > 0 THEN 1 ELSE 0 END + CASE WHEN MDEF > 0 THEN 1 ELSE 0 END + CASE WHEN SPD > 0 THEN 1 ELSE 0 END)"
        negative_stat_count_logic = "(CASE WHEN ATK < 0 THEN 1 ELSE 0 END + CASE WHEN DEF < 0 THEN 1 ELSE 0 END + CASE WHEN MATK < 0 THEN 1 ELSE 0 END + CASE WHEN MDEF < 0 THEN 1 ELSE 0 END + CASE WHEN SPD < 0 THEN 1 ELSE 0 END)"
        single_stat_logic = f"(({positive_stat_count_logic} = 1 AND {negative_stat_count_logic} <= 1) OR ({positive_stat_count_logic} = 0 AND {negative_stat_count_logic} = 1))"
        multi_stat_logic = f"(({positive_stat_count_logic} > 1) OR ({positive_stat_count_logic} = 1 AND {negative_stat_count_logic} > 1) OR ({positive_stat_count_logic} = 0 AND {negative_stat_count_logic} > 1))"
        conditions, params = [], []
        if self.species_listbox.curselection():
            selected_species = self.species_listbox.get(self.species_listbox.curselection()[0])
            if selected_species != '全部': conditions.append("species = ?"); params.append(selected_species)
        keyword = self.filters['keyword'].get().strip()
        if keyword:
            conditions.append("(name LIKE ? OR formula LIKE ? OR reference LIKE ? OR reference_beginner LIKE ?)")
            params.extend([f"%{keyword}%"] * 4)
        selected_parts = [part for part, var in self.filters['parts'].items() if var.get()]
        if selected_parts:
            placeholders = ', '.join(['?'] * len(selected_parts))
            conditions.append(f"part IN ({placeholders})");
            params.extend(selected_parts)
        stat_count_choice = self.filters['stat_count'].get()
        if stat_count_choice == '單屬性':
            conditions.append(single_stat_logic)
        elif stat_count_choice == '多屬性':
            conditions.append(multi_stat_logic)
        elif stat_count_choice == '無屬性':
            conditions.append(f"{stat_count_logic} = 0")
        for stat in ['ATK', 'DEF', 'MATK', 'MDEF', 'SPD']:
            min_val, max_val = self.filters[f'{stat}_min'].get().strip(), self.filters[f'{stat}_max'].get().strip()
            if min_val.isdigit() and max_val.isdigit():
                conditions.append(f"{stat} BETWEEN ? AND ?"); params.extend([int(min_val), int(max_val)])
            elif min_val.isdigit():
                conditions.append(f"{stat} >= ?"); params.append(int(min_val))
            elif max_val.isdigit():
                conditions.append(f"{stat} <= ?"); params.append(int(max_val))
        final_query = base_query
        if conditions: final_query += " WHERE " + " AND ".join(conditions)
        if self.sort_by:
            db_col = self.column_map.get(self.sort_by, self.sort_by)
            order = "DESC" if self.sort_descending else "ASC"
            final_query += f" ORDER BY {db_col} {order}"
        else:
            final_query += " ORDER BY id"
        data = self.run_query(final_query, tuple(params))
        self.populate_tree(data)

    def reset_filters(self):
        selected_ids = self.get_selected_tree_ids()
        self.species_listbox.selection_clear(0, 'end')
        self.species_listbox.selection_set(0)
        self.filters['keyword'].delete(0, 'end')
        for var in self.filters['parts'].values(): var.set(False)
        self.filters['stat_count'].set('全部')
        for stat in ['ATK', 'DEF', 'MATK', 'MDEF', 'SPD']:
            self.filters[f'{stat}_min'].delete(0, 'end');
            self.filters[f'{stat}_max'].delete(0, 'end')
        self.sort_by = None
        self.apply_filters()
        self.after(100, lambda: self.restore_tree_selection(selected_ids, scroll_to_focus=True))

    # 刷新方法
    def refresh_all(self):
        """刷新所有資料和介面元件，並恢復視圖和篩選條件。"""
        print("正在刷新介面...")

        # 1. 記住 Treeview 狀態 (物種選擇的恢復交給 populate_filter_options)
        selected_ids = self.get_selected_tree_ids()
        scroll_pos = self.tree.yview()

        # 2. 刷新篩選器選項 (新版的 populate 會自己處理選擇恢復)
        self.populate_filter_options()

        # 3. 重新應用篩選
        self.apply_filters()

        # 4. 恢復 Treeview 的狀態
        self.after(100, lambda: self.tree.yview_moveto(scroll_pos[0]))
        if selected_ids:  # 只有在之前有選中項時才嘗試恢復
            self.restore_tree_selection(selected_ids)

    def get_selected_tree_ids(self):
        """取得目前選取或聚焦列的資料 ID。"""
        selected_items = list(self.tree.selection())
        focused_item = self.tree.focus()
        if focused_item and focused_item not in selected_items:
            selected_items.append(focused_item)
        selected_ids = []
        for item in selected_items:
            values = self.tree.item(item).get('values', [])
            if values:
                selected_ids.append(str(values[0]))
        return selected_ids

    def restore_tree_selection(self, selected_ids, scroll_to_focus=False):
        """依資料 ID 恢復 Treeview 選取狀態。"""
        if not selected_ids:
            return

        new_items_map = {
            str(self.tree.item(item)['values'][0]): item
            for item in self.tree.get_children()
            if self.tree.item(item).get('values')
        }
        restored_items = [new_items_map[item_id] for item_id in selected_ids if item_id in new_items_map]
        if not restored_items:
            return

        self.tree.selection_set(restored_items)
        self.tree.focus(restored_items[0])
        if scroll_to_focus:
            self.tree.see(restored_items[0])

    # 其他方法... (run_query, populate_tree, 排序, 欄寬調整, 新增/修改等)
    def run_query(self, query, params=()):
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            messagebox.showerror("資料庫錯誤", f"查詢失敗：{e}")
            return []
        finally:
            if conn: conn.close()

    def populate_tree(self, data):
        self.tree.delete(*self.tree.get_children())
        lower_case_data = [{k.lower(): v for k, v in row_dict.items()} for row_dict in data]
        for index, row_dict in enumerate(lower_case_data):
            values_in_order = []
            for col_display_name in self.columns_order:
                db_col_name = self.column_map[col_display_name].lower()
                value = row_dict.get(db_col_name)
                values_in_order.append('' if value is None else str(value))
            row_tag = 'evenrow' if index % 2 == 0 else 'oddrow'
            self.tree.insert('', 'end', values=values_in_order, tags=(row_tag,))

    def on_header_double_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "separator":
            col_id = self.tree.identify_column(event.x)
            self.auto_adjust_column_width(self.tree.column(col_id, "id"))

    def auto_adjust_column_width(self, col_display_name):
        try:
            font = tkFont.nametofont("TkDefaultFont")
        except tk.TclError:
            font = tkFont.Font(family="Arial", size=10)
        max_width = font.measure(col_display_name + '  ')
        for item in self.tree.get_children('')[:100]:
            cell_value = self.tree.set(item, col_display_name)
            if cell_value:
                required_width = font.measure(cell_value)
                if required_width > max_width: max_width = required_width
        self.tree.column(col_display_name, width=max_width + 10)

    def on_header_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            self.sort_by_column(self.tree.column(self.tree.identify_column(event.x), 'id'))

    def on_tree_motion(self, event):
        """當滑鼠在 Treeview 上移動時觸發，用於顯示儲存格的 Tooltip。"""
        # 獲取當前滑鼠下的儲存格標識 (行ID + 欄ID)
        item_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        current_cell = (item_id, col_id)

        # 1. 檢查滑鼠是否移動到了新的儲存格
        if current_cell != self._last_tooltip_cell:
            # 如果是新的儲存格，立即隱藏舊的 tooltip
            self.tooltip.hidetip()
            # 取消之前所有待顯示的 tooltip 任務
            if self._tooltip_after_id:
                self.after_cancel(self._tooltip_after_id)
                self._tooltip_after_id = None

            # 更新最後的儲存格記錄
            self._last_tooltip_cell = current_cell

            # 2. 判斷新的儲存格是否需要顯示 tooltip
            if item_id and col_id:
                col_name = self.tree.column(col_id, "id")
                if col_name in ['名稱', '公式', '參考配方', '參考配方(初階)', '其他']:
                    cell_text = self.tree.set(item_id, col_name)
                    if cell_text:
                        # 3. 安排一個新的延時任務來顯示 tooltip
                        #    將事件物件和文字內容傳遞過去
                        self._tooltip_after_id = self.after(
                            500,  # 延遲 500 毫秒
                            lambda e=event, t=cell_text: self.show_tooltip_for_cell(t, e)
                        )

    def show_tooltip_for_cell(self, text, event):
        """一個輔助函式，用於被 after 調用來顯示 tooltip"""
        # 在顯示前，再次檢查滑鼠是否還在同一個位置，防止滑鼠已移走但tooltip還彈出
        item_id = self.tree.identify_row(event.y)
        col_id = self.tree.identify_column(event.x)
        if (item_id, col_id) == self._last_tooltip_cell:
            self.tooltip.showtip(text, event)

    def sort_by_column(self, col_display_name):
        db_col_name = self.column_map.get(col_display_name, col_display_name)
        if self.sort_by == col_display_name:
            self.sort_descending = not self.sort_descending
        else:
            self.sort_by = col_display_name; self.sort_descending = False
        self.apply_filters()  # 點擊排序後直接重新查詢，更簡單可靠

    def batch_add_recipes(self):
        BatchRecipeImporter(self)

    def modify_recipe(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("提示", "請先在右側表格中選擇一個要修改的配方！")
            return
        item_values = self.tree.item(selected_item)['values']
        id_index = self.columns_order.index('ID')
        item_id = item_values[id_index]
        RecipeEditor(self, item_id=item_id)

    def delete_recipe(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning("提示", "請先在右側表格中選擇要刪除的配方！")
            return

        id_index = self.columns_order.index('ID')
        id_to_name = {}
        for item in selected_items:
            values = self.tree.item(item)['values']
            id_to_name[values[id_index]] = values[self.columns_order.index('名稱')]

        names_preview = '、'.join(str(n) for n in list(id_to_name.values())[:10])
        if len(id_to_name) > 10:
            names_preview += "..."
        if not messagebox.askyesno(
            "確認刪除",
            f"確定要刪除以下 {len(id_to_name)} 筆配方嗎？此操作無法復原。\n\n{names_preview}"
        ):
            return

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        try:
            placeholders = ', '.join(['?'] * len(id_to_name))
            cursor.execute(f"DELETE FROM recipes WHERE id IN ({placeholders})", tuple(id_to_name.keys()))
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("資料庫錯誤", f"刪除失敗：{e}")
            return
        finally:
            conn.close()

        messagebox.showinfo("成功", f"已刪除 {len(id_to_name)} 筆配方。")
        self.refresh_all()


    def open_url(self, url):
        """在新瀏覽器分頁中打開指定的 URL"""
        try:
            webbrowser.open_new_tab(url)
            print(f"嘗試打開連結: {url}")
        except Exception as e:
            messagebox.showerror("錯誤", f"無法打開連結：\n{url}\n\n錯誤訊息: {e}")

    def update_font(self, event=None):
        """更新整個應用程式的字體"""
        new_family = self.font_family_combo.get()
        new_size = int(self.font_size_combo.get())

        self.font_family.set(new_family)
        self.font_size.set(new_size)

        # 定義要更新的字體
        new_font = (new_family, new_size)

        # --- 更新 ttk 元件的預設字體 ---
        self.style.configure('.', font=new_font)
        self.style.configure('TLabelframe.Label', font=(new_family, new_size, 'bold'))
        self.style.configure('Treeview.Heading', font=(new_family, new_size, 'bold'))

        # --- 更新非 ttk 元件的字體 ---
        # 左側物種列表
        self.species_listbox.config(font=new_font)
        # 連結標籤 (如果需要的話)
        # for child in self.source_frame.winfo_children():
        #     if isinstance(child, tk.Label):
        #         child.config(font=(new_family, new_size, "underline"))

        # 重新調整一下 Treeview 的行高以適應新字體
        self.style.configure("Treeview", rowheight=new_size + 14)
        self.tree.tag_configure('evenrow', background=self.colors["row_even"])
        self.tree.tag_configure('oddrow', background=self.colors["row_odd"])

if __name__ == "__main__":
    app = App()
    app.mainloop()
