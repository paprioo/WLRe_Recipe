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

        label = ttk.Label(tw, text=text, justify=tk.LEFT,
                          background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                          wraplength=500)
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
        data_to_save = {key: entry.get() for key, entry in self.entries.items()}
        if not data_to_save['name'] or not data_to_save['species']:
            messagebox.showwarning("輸入錯誤", "「名稱」和「物種」為必填欄位！")
            return

        stats_str = data_to_save['stats']
        parsed_stats = parse_stats(stats_str)

        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        try:
            # vvv--- 這是核心修正：確保 data_tuple 有 14 個元素 ---vvv
            data_tuple = (
                data_to_save['species'],
                data_to_save['level'] or None,
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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("飄流幻境煉金查詢器")
        self.geometry("1400x800")
        self.sort_by = None
        self.sort_descending = False

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
    def create_widgets(self):
        main_pane = ttk.PanedWindow(self, orient='horizontal')
        main_pane.pack(expand=True, fill='both', padx=10, pady=5)

        # --- 左側 ---
        left_frame = ttk.Frame(main_pane)  # 我們不再需要 Labelframe
        main_pane.add(left_frame, weight=0)

        # --- 左側上方：物種列表 ---
        species_frame = ttk.Labelframe(left_frame, text="物種列表")
        species_frame.pack(expand=True, fill='both')
        self.species_listbox = tk.Listbox(species_frame, exportselection=False)
        self.species_listbox.pack(expand=True, fill='both', padx=5, pady=5)
        self.species_listbox.bind('<<ListboxSelect>>', lambda event: self.apply_filters())

        # vvv--- 新增這個區塊：左側下方：資料來源 ---vvv
        source_frame = ttk.Labelframe(left_frame, text="資料參考來源")
        source_frame.pack(side='bottom', fill='x', pady=(10, 0))

        # 定義超連結的文字和對應的網址
        links = {
            "巴哈姆特鍊金百科(tonytony7310)": "https://forum.gamer.com.tw/G1.php?bsn=8897&parent=5247",
            "巴哈姆特[星耀]屬爬等表(nrmk132475)": "https://forum.gamer.com.tw/C.php?bsn=82442&snA=139&tnum=5",
            "裝備合成表(aska2500)": "https://nextjs-github-vercel.vercel.app/"
        }

        # 創建超連結標籤
        for text, url in links.items():
            link_label = tk.Label(source_frame, text=text, fg="blue", cursor="hand2")
            link_label.pack(anchor='w', padx=5, pady=2)
            # 使用 lambda 來確保每個標籤都綁定到正確的 URL
            link_label.bind("<Button-1>", lambda event, link=url: self.open_url(link))
        # ^^^-------------------------------------------------^^^

        # 右側
        right_container = ttk.Frame(main_pane)
        main_pane.add(right_container, weight=1)
        filter_area = ttk.Frame(right_container);
        filter_area.pack(side='top', fill='x', pady=5)

        # 篩選器元件的創建...
        kw_frame = ttk.Frame(filter_area);
        kw_frame.pack(fill='x', anchor='w', pady=2)
        ttk.Label(kw_frame, text="關鍵字搜尋:").pack(side='left', padx=(0, 5))
        self.filters['keyword'] = ttk.Entry(kw_frame);
        self.filters['keyword'].pack(side='left', expand=True, fill='x')
        # vvv--- 新增這一行事件綁定 ---vvv
        # 當使用者在 Entry 中按下 Enter 鍵 (<Return>) 時，呼叫 apply_filters 方法
        self.filters['keyword'].bind('<Return>', lambda event: self.apply_filters())
        # ^^^--------------------------^^^

        self.part_frame = ttk.Labelframe(filter_area, text="部位 (可多選)");
        self.part_frame.pack(fill='x', pady=3, anchor='w')
        self.filters['parts'] = {}

        stat_count_frame = ttk.Labelframe(filter_area, text="屬性數量");
        stat_count_frame.pack(fill='x', pady=3, anchor='w')
        self.filters['stat_count'] = tk.StringVar(value="全部")
        for option in ['全部', '單屬性', '多屬性', '無屬性']:
            rb = ttk.Radiobutton(stat_count_frame, text=option, variable=self.filters['stat_count'], value=option).pack(
                side='left', padx=5)

        stats_frame = ttk.Labelframe(filter_area, text="數值範圍篩選");
        stats_frame.pack(fill='x', pady=3, anchor='w')
        for stat in ['ATK', 'DEF', 'MATK', 'MDEF', 'SPD']:
            stat_group = ttk.Frame(stats_frame);
            stat_group.pack(side='left', padx=(0, 15));
            ttk.Label(stat_group, text=f"{stat}").pack()
            entry_group = ttk.Frame(stat_group);
            entry_group.pack()
            self.filters[f'{stat}_min'] = ttk.Entry(entry_group, width=5);
            self.filters[f'{stat}_min'].pack(side='left')
            ttk.Label(entry_group, text="-").pack(side='left', padx=2)
            self.filters[f'{stat}_max'] = ttk.Entry(entry_group, width=5);
            self.filters[f'{stat}_max'].pack(side='left')

        button_frame = ttk.Frame(filter_area);
        button_frame.pack(fill='x', pady=(5, 0))
        ttk.Button(button_frame, text="應用篩選", command=self.apply_filters).pack(side='left')
        ttk.Button(button_frame, text="重設篩選", command=self.reset_filters).pack(side='left', padx=5)
        ttk.Button(button_frame, text="新增配方", command=self.add_recipe).pack(side='right', padx=5)
        ttk.Button(button_frame, text="修改選定配方", command=self.modify_recipe).pack(side='right')

        tree_frame = ttk.Frame(right_container);
        tree_frame.pack(expand=True, fill='both', pady=(5, 0))
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

    def populate_filter_options(self):
        self.species_listbox.delete(0, 'end')
        self.species_listbox.insert('end', "全部")
        species_data = self.run_query(
            "SELECT DISTINCT species FROM recipes WHERE species IS NOT NULL AND species != '' ORDER BY species")
        for row in species_data: self.species_listbox.insert('end', row['species'])
        self.species_listbox.selection_set(0)
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

    def apply_filters(self):
        # apply_filters 的邏輯是正確的，保持不變
        base_query = "SELECT * FROM recipes"
        stat_count_logic = "(CASE WHEN ATK NOT NULL AND ATK!=0 THEN 1 ELSE 0 END + CASE WHEN DEF NOT NULL AND DEF!=0 THEN 1 ELSE 0 END + CASE WHEN MATK NOT NULL AND MATK!=0 THEN 1 ELSE 0 END + CASE WHEN MDEF NOT NULL AND MDEF!=0 THEN 1 ELSE 0 END + CASE WHEN SPD NOT NULL AND SPD!=0 THEN 1 ELSE 0 END)"
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
            conditions.append(f"{stat_count_logic} = 1")
        elif stat_count_choice == '多屬性':
            conditions.append(f"{stat_count_logic} > 1")
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
        self.species_listbox.selection_clear(0, 'end');
        self.species_listbox.selection_set(0)
        self.filters['keyword'].delete(0, 'end')
        for var in self.filters['parts'].values(): var.set(False)
        self.filters['stat_count'].set('全部')
        for stat in ['ATK', 'DEF', 'MATK', 'MDEF', 'SPD']:
            self.filters[f'{stat}_min'].delete(0, 'end');
            self.filters[f'{stat}_max'].delete(0, 'end')
        self.sort_by = None
        self.apply_filters()

    # 刷新方法
    def refresh_all(self):
        """
        刷新所有資料和介面元件。在新增或修改資料後呼叫。
        """
        print("正在刷新介面...")
        self.populate_filter_options()
        self.apply_filters()

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
        for row_dict in lower_case_data:
            values_in_order = []
            for col_display_name in self.columns_order:
                db_col_name = self.column_map[col_display_name].lower()
                value = row_dict.get(db_col_name)
                values_in_order.append('' if value is None else str(value))
            self.tree.insert('', 'end', values=values_in_order)

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

    def add_recipe(self):
        RecipeEditor(self)

    def modify_recipe(self):
        selected_item = self.tree.focus()
        if not selected_item:
            messagebox.showwarning("提示", "請先在右側表格中選擇一個要修改的配方！")
            return
        item_values = self.tree.item(selected_item)['values']
        id_index = self.columns_order.index('ID')
        item_id = item_values[id_index]
        RecipeEditor(self, item_id=item_id)

    def open_url(self, url):
        """在新瀏覽器分頁中打開指定的 URL"""
        try:
            webbrowser.open_new_tab(url)
            print(f"嘗試打開連結: {url}")
        except Exception as e:
            messagebox.showerror("錯誤", f"無法打開連結：\n{url}\n\n錯誤訊息: {e}")


if __name__ == "__main__":
    app = App()
    app.mainloop()