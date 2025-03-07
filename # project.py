from sklearn.metrics.pairwise import cosine_similarity
import discord
from discord import app_commands
from discord.ext import commands
import sqlite3
import datetime
import pandas as pd
import pickle
from surprise import Dataset, Reader, SVDpp, accuracy
from surprise.model_selection import train_test_split
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import config
import tmp
import json
import coupon_recommende 
import single
import spacy
import difflib
nlp = spacy.load("custom_ner_model")


menu = single.get_single()  

#暫存使用者的訂單、評價與套餐選擇資料
user_temp_orders = {}     
user_temp_ratings = {}     
user_temp_packages = {}    

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=config.PREFIX, intents=intents)
model = None
scheduler = AsyncIOScheduler()


def init_db():
    conn_orders = sqlite3.connect("orders.db")
    cursor_orders = conn_orders.cursor()
    cursor_orders.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            user_id INTEGER,
            item TEXT,
            quantity INTEGER,
            timestamp TEXT,
            PRIMARY KEY (user_id, item)
        )
    """)
    conn_orders.commit()
    conn_orders.close()

    conn_ratings = sqlite3.connect("rating.db")
    cursor_ratings = conn_ratings.cursor()#database收集資料
    cursor_ratings.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            user_id INTEGER,
            item TEXT,
            rating INTEGER,
            timestamp TEXT,
            PRIMARY KEY (user_id, item)
        )
    """)
    conn_ratings.commit()
    conn_ratings.close()

def record_rating(user_id, item, rating):
    conn = sqlite3.connect("rating.db")
    cursor = conn.cursor()
    current_time = datetime.datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO ratings (user_id, item, rating, timestamp)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, item) DO UPDATE SET
        rating=excluded.rating, timestamp=excluded.timestamp
    """, (user_id, item, rating, current_time))
    conn.commit()
    conn.close()

def record_order(user_id, item, quantity):
    conn = sqlite3.connect("orders.db")
    cursor = conn.cursor()
    current_time = datetime.datetime.now().isoformat()
    cursor.execute("""
        INSERT INTO orders (user_id, item, quantity, timestamp)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, item) DO UPDATE SET timestamp=excluded.timestamp
    """, (user_id, item, quantity, current_time))
    conn.commit()
    conn.close()

#SVD++數據採集
def fetch_ratings():
    conn = sqlite3.connect("rating.db")
    df = pd.read_sql_query("SELECT user_id, item, rating FROM ratings", conn)
    conn.close()
    return df

def train_model():
    df = fetch_ratings()
    if df.empty:
        print("尚無數據進行訓練。")
        return None

    reader = Reader(rating_scale=(1, 5))
    data = Dataset.load_from_df(df[['user_id', 'item', 'rating']], reader)
    trainset, testset = train_test_split(data, test_size=0.2)

    algo = SVDpp()
    algo.fit(trainset)
    predictions = algo.test(testset)
    rmse = accuracy.rmse(predictions)
    print(f"模型訓練完成。RMSE: {rmse}")

    with open("recommend_model.pkl", "wb") as f:
        pickle.dump(algo, f)
    return algo

def load_model():
    global model
    try:
        with open("recommend_model.pkl", "rb") as f:
            model = pickle.load(f)
        print("成功載入模型。")
    except FileNotFoundError:
        print("找不到模型檔案，開始訓練新模型...")
        model = train_model()
    return model

def get_recommendations(user_id, top_n=3):
    if model is None:
        return "模型尚未建立。"
    all_products = {}
    for category in menu.values():
        all_products.update(category)
    recommendations = {product: model.predict(user_id, product).est for product in all_products.keys()}
    sorted_recs = sorted(recommendations.items(), key=lambda x: x[1], reverse=True)
    return sorted_recs[:top_n]

# APScheduler 定時更新模型
def update_model_job():
    global model
    print("開始更新推薦模型...")
    new_model = train_model()
    if new_model:
        model = new_model
        print("模型更新完成！")

scheduler.add_job(update_model_job, 'cron', hour=0, minute=0)
scheduler.add_job(tmp.main, 'cron', hour=0, minute=0)


class RatingCategorySelect(discord.ui.Select):
    def __init__(self, menu: dict):
        options = [discord.SelectOption(label=cat, description=f"{cat}料理") for cat in menu.keys()]
        super().__init__(placeholder="請選擇要評價的料理類別", min_values=1, max_values=1, options=options)
        self.menu = menu

    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]
        food_dict = self.menu.get(selected_category, {})
        if not food_dict:
            await interaction.response.send_message("該類別沒有食物選項。", ephemeral=True)
            return
        view = RatingCategoryFoodSelectConfirmView(food_dict, selected_category, self.menu)
        await interaction.response.send_message(f"您選擇了 **{selected_category}**，請選擇要評價的食物（可多選）：", view=view, ephemeral=True)

class RatingCategoryView(discord.ui.View):
    def __init__(self, menu: dict):
        super().__init__()
        self.add_item(RatingCategorySelect(menu))

class RatingCategoryFoodSelect(discord.ui.Select):
    def __init__(self, food_dict: dict, category: str):
        options = [discord.SelectOption(label=food, description=f"價格：{price} 元")
                   for food, price in food_dict.items()]
        super().__init__(placeholder=f"請選擇 {category} 中的食物 (可多選)",
                         min_values=1, max_values=len(options), options=options)
        self.food_dict = food_dict
        self.category = category

    async def callback(self, interaction: discord.Interaction):
        if not self.values:
            await interaction.response.send_message("請先選擇至少一個食物。", ephemeral=True)
            return
        modal = CategoryRatingModal(self.values, self.food_dict, self.category)
        await interaction.response.send_modal(modal)

class RatingCategoryBackButton(discord.ui.Button):
    def __init__(self, menu: dict):
        super().__init__(label="返回上一層", style=discord.ButtonStyle.secondary)
        self.menu = menu

    async def callback(self, interaction: discord.Interaction):
        view = RatingCategoryView(self.menu)
        await interaction.response.edit_message(content="請先選擇要評價的料理類別：", view=view)

class RatingCategoryFoodSelectConfirmView(discord.ui.View):
    def __init__(self, food_dict: dict, category: str, menu: dict):
        super().__init__()
        self.add_item(RatingCategoryFoodSelect(food_dict, category))
        self.add_item(RatingCategoryBackButton(menu))

class CategoryRatingModal(discord.ui.Modal, title="請輸入各食物評分 (1~5)"):
    def __init__(self, selected_foods: list, food_dict: dict, category: str):
        super().__init__()
        self.selected_foods = selected_foods
        self.food_dict = food_dict
        self.category = category
        for food in selected_foods:
            self.add_item(discord.ui.TextInput(
                label=f"{food} 評分 (1~5)",
                placeholder="請輸入評分",
                default="5",
                required=True
            ))
    
    async def on_submit(self, interaction: discord.Interaction):
        responses = []
        ratings = user_temp_ratings.setdefault(interaction.user.id, {})
        for food, text_input in zip(self.selected_foods, self.children):
            try:
                rating = int(text_input.value)
            except ValueError:
                rating = 5
            if rating < 1 or rating > 5:
                rating = 5
            ratings[food] = rating
            responses.append(f"{food} 評分: {rating}")
        summary_lines = []
        for food, rating in ratings.items():
            summary_lines.append(f"{food} 評分: {rating}")
        summary_text = "\n".join(summary_lines)
        response_text = f"您在 **{self.category}** 的評價：\n" + "\n".join(responses) + "\n\n目前累積評價：\n" + summary_text
        await interaction.response.send_message(response_text, ephemeral=True)
        await interaction.followup.send("請繼續評價其他類別，或點選下方【確認評價】以送出累積評價：", view=RatingSelectionView(), ephemeral=True)

class RatingSelectionView(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.add_item(ConfirmRatingButton())
        self.add_item(RemoveRatingButton())

class ConfirmRatingButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="確認評價", style=discord.ButtonStyle.success)
    async def callback(self, interaction: discord.Interaction):
        ratings = user_temp_ratings.get(interaction.user.id, {})
        if not ratings:
            await interaction.response.send_message("您尚未輸入任何評價。", ephemeral=True)
            return
        for food, rating in ratings.items():
            record_rating(interaction.user.id, food, rating)
        await interaction.response.send_message("您的評價已送出！", ephemeral=True)
        user_temp_ratings.pop(interaction.user.id, None)

class RemoveRatingButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="刪除評價", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        ratings = user_temp_ratings.get(interaction.user.id, {})
        if not ratings:
            await interaction.response.send_message("目前沒有評價可以刪除。", ephemeral=True)
            return
        view = RemoveRatingView(ratings)
        await interaction.response.send_message("請選擇要刪除的評價項目：", view=view, ephemeral=True)

class RemoveRatingSelect(discord.ui.Select):
    def __init__(self, ratings: dict):
        options = []
        for food, rating in ratings.items():
            options.append(discord.SelectOption(label=food, description=f"目前評分：{rating}", value=food))
        super().__init__(placeholder="選擇要刪除的評價項目（可多選）", min_values=1, max_values=len(options), options=options)
    async def callback(self, interaction: discord.Interaction):
        ratings = user_temp_ratings.get(interaction.user.id, {})
        removed_items = []
        for food in self.values:
            if food in ratings:
                removed_items.append(food)
                del ratings[food]
        msg = ""
        if removed_items:
            msg += "已刪除：" + ", ".join(removed_items) + "\n"
        else:
            msg += "未刪除任何評價項目。\n"
        summary_lines = []
        for food, rating in ratings.items():
            summary_lines.append(f"{food} 評分: {rating}")
        if summary_lines:
            summary_text = "\n".join(summary_lines)
            msg += "目前累積評價：\n" + summary_text
        else:
            msg += "目前無累積評價。"
        await interaction.response.send_message(msg, ephemeral=True)

class RemoveRatingView(discord.ui.View):
    def __init__(self, ratings: dict):
        super().__init__()
        self.add_item(RemoveRatingSelect(ratings))


class PackageCategorySelect(discord.ui.Select):#選擇類別
    def __init__(self, menu: dict):
        options = [discord.SelectOption(label=cat, description=f"{cat}料理") for cat in menu.keys()]
        super().__init__(placeholder="請選擇套餐品項的類別", min_values=1, max_values=1, options=options)
        self.menu = menu
    async def callback(self, interaction: discord.Interaction):
        selected_category = self.values[0]
        food_dict = self.menu.get(selected_category, {})
        if not food_dict:
            await interaction.response.send_message("該類別沒有品項。", ephemeral=True)
            return
        view = PackageFoodSelectConfirmView(food_dict, selected_category, self.menu)
        await interaction.response.send_message(f"您選擇了 **{selected_category}**，請選擇品項（可多選）：", view=view, ephemeral=True)

class RecommendedPackageSelect(discord.ui.Select):#列印套餐
    def __init__(self, recommended_packages: list):
        options = []
        # 推薦套餐資料格式：{ "total_price": ..., "packages": ... }
        for idx, rec in enumerate(recommended_packages):
            total_price = rec["total_price"]
            package = rec["packages"]
            if(idx == 0):
                label = f"單點 - 總價: {total_order_price}元"
                description = "內容：" + str(package)[:80]
                options.append(discord.SelectOption(label=label, description=description, value=str(idx)))
            else:
                label = f"方案 {idx+1} - 總價: {total_price}元"
                description = "內容：" + str(package)[:80]
                options.append(discord.SelectOption(label=label, description=description, value=str(idx)))
        super().__init__(placeholder="請選擇推薦的套餐", min_values=1, max_values=1, options=options)
        self.recommended_packages = recommended_packages

    async def callback(self, interaction: discord.Interaction):
        idx = int(self.values[0])
        selected_package = self.recommended_packages[idx]
        total_price = selected_package["total_price"]
        packages = selected_package["packages"]
        content = json.dumps(packages, ensure_ascii=False, indent=2)
        await interaction.response.send_message(
            f"您選擇了方案 {idx+1}：\n總價: {total_price}元\n內容:\n{content}",
            ephemeral=True
        )

class RecommendedPackageView(discord.ui.View):
    def __init__(self, recommended_packages: list):
        super().__init__()
        self.add_item(RecommendedPackageSelect(recommended_packages))

class PackageConfirmButton(discord.ui.Button):#累積選擇後確認
    def __init__(self):
        super().__init__(label="確認套餐選擇", style=discord.ButtonStyle.success)
    async def callback(self, interaction: discord.Interaction):
        packages = user_temp_packages.get(interaction.user.id, {})
        if not packages:
            await interaction.response.send_message("您尚未選擇任何品項。", ephemeral=True)
            return

        recommended_packages = coupon_recommende.coupon_recommender(packages)
        if not recommended_packages:
            await interaction.response.send_message("找不到推薦套餐。", ephemeral=True)
            return

        details_message = "根據您的累積選擇，以下是推薦套餐：\n\n"
        for idx, rec in enumerate(recommended_packages):
            total_price = rec["total_price"]
            package_detail = rec["packages"]
            if(idx == 0):
                details_message += f"單點 - 總價: {total_order_price}元"
            else:
                details_message += f"方案 {idx+1} - 總價: {total_price}元"
            for coupon_code, steps in package_detail.items():
                details_message += f"  {coupon_code}:\n"
                for step in steps:
                    for item, qty in step.items():
                        details_message += f"    {item}: {qty}\n"
            details_message += "\n"

        view = RecommendedPackageView(recommended_packages)
        await interaction.response.send_message(details_message, view=view, ephemeral=True)
        user_temp_packages.pop(interaction.user.id, None)

class RemovePackageSelect(discord.ui.Select):
    def __init__(self, packages: dict):
        options = []
        for food, qty in packages.items():
            options.append(discord.SelectOption(label=food, description=f"目前數量：{qty}", value=food))
        super().__init__(
            placeholder="選擇要刪除的品項（可多選）",
            min_values=1,
            max_values=len(options),
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        packages = user_temp_packages.get(interaction.user.id, {})
        removed_items = []
        for food in self.values:
            if food in packages:
                removed_items.append(food)
                del packages[food]
        msg = ""
        if removed_items:
            msg += "已刪除：" + ", ".join(removed_items) + "\n"
        else:
            msg += "未刪除任何品項。\n"
        summary_lines = []
        total_order_price = 0
        for food, qty in packages.items():
            food_price = 0
            for cat, items in menu.items():
                if food in items:
                    food_price = items[food]
                    break
            summary_lines.append(f"{food} x {qty}（{food_price} 元/個）")
            total_order_price += qty * food_price
        if summary_lines:
            summary_text = "\n".join(summary_lines)
            msg += f"目前累積套餐選擇：\n{summary_text}\n總金額：{total_order_price} 元"
        else:
            msg += "目前無累積套餐選擇。"
        await interaction.response.send_message(msg, ephemeral=True)

class RemovePackageView(discord.ui.View):
    def __init__(self, packages: dict):
        super().__init__()
        self.add_item(RemovePackageSelect(packages))

class PackageRemoveButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="刪除品項", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        packages = user_temp_packages.get(interaction.user.id, {})
        if not packages:
            await interaction.response.send_message("目前沒有品項可以刪除。", ephemeral=True)
            return
        view = RemovePackageView(packages)
        await interaction.response.send_message("請選擇要刪除的品項：", view=view, ephemeral=True)

class PackageSelectionView(discord.ui.View):
    def __init__(self, menu: dict):
        super().__init__()
        self.add_item(PackageCategorySelect(menu))
        self.add_item(PackageConfirmButton())
        self.add_item(PackageRemoveButton())

class PackageCategoryBackButton(discord.ui.Button):
    def __init__(self, menu: dict):
        super().__init__(label="返回上一層", style=discord.ButtonStyle.secondary)
        self.menu = menu
    async def callback(self, interaction: discord.Interaction):
        view = PackageSelectionView(self.menu)
        await interaction.response.edit_message(content="請選擇套餐類別：", view=view)

class PackageFoodSelect(discord.ui.Select):
    def __init__(self, food_dict: dict, category: str):
        options = [discord.SelectOption(label=food, description=f"價格：{price} 元") for food, price in food_dict.items()]
        super().__init__(placeholder=f"請選擇 {category} 中的品項 (可多選)", min_values=1, max_values=len(options), options=options)
        self.food_dict = food_dict
        self.category = category
    async def callback(self, interaction: discord.Interaction):
        if not self.values:
            await interaction.response.send_message("請先選擇至少一個品項。", ephemeral=True)
            return
        modal = PackageFoodQuantityModal(self.values, self.food_dict, self.category)
        await interaction.response.send_modal(modal)

class PackageFoodSelectConfirmView(discord.ui.View):
    def __init__(self, food_dict: dict, category: str, menu: dict):
        super().__init__()
        self.add_item(PackageFoodSelect(food_dict, category))
        self.add_item(PackageCategoryBackButton(menu))

class PackageFoodQuantityModal(discord.ui.Modal, title="請輸入各品項數量"):
    def __init__(self, selected_items: list, food_dict: dict, category: str):
        super().__init__()
        self.selected_items = selected_items
        self.food_dict = food_dict
        self.category = category
        for food in selected_items:
            self.add_item(discord.ui.TextInput(
                label=f"{food} 數量",
                placeholder="請輸入數量（整數）",
                default="1",
                required=True
            ))
    async def on_submit(self, interaction: discord.Interaction):
        responses = []
        total_price = 0
        packages = user_temp_packages.setdefault(interaction.user.id, {})
        for food, text_input in zip(self.selected_items, self.children):
            try:
                quantity = int(text_input.value)
            except ValueError:
                quantity = 1
            packages[food] = packages.get(food, 0) + quantity
            price = self.food_dict.get(food, 0)
            responses.append(f"{food} x {quantity}（{price} 元）")
            total_price += price * quantity
        summary_lines = []
        global total_order_price
        total_order_price = 0
        for food, qty in packages.items():
            food_price = 0
            for cat, items in menu.items():
                if food in items:
                    food_price = items[food]
                    break
            summary_lines.append(f"{food} x {qty}（{food_price} 元/個）")
            total_order_price += qty * food_price
        summary_text = "\n".join(summary_lines)
        response_text = (
            f"您在 **{self.category}** 選擇了：\n" +
            "\n".join(responses) +
            f"\n本次類別小計：{total_price} 元\n\n" +
            f"目前累積的套餐選擇：\n{summary_text}\n" +
            f"總金額：{total_order_price} 元"
        )
        await interaction.response.send_message(response_text, ephemeral=True)
        await interaction.followup.send("請繼續選擇其他類別，或點選下方【確認套餐選擇】以獲得推薦套餐：", view=PackageSelectionView(menu), ephemeral=True)

@bot.event
async def on_ready():
    print(f"✅ Bot {bot.user} 已上線！")
    init_db()
    load_model()
    scheduler.start()
    try:
        synced = await bot.tree.sync()
        print(f"📌 已同步 {len(synced)} 個應用指令")
    except Exception as e:
        print(f"❌ 指令同步失敗：{e}")

@bot.tree.command(name="菜單", description="顯示產品菜單")
async def menu_command(interaction: discord.Interaction):
    menu_text_lines = []
    for category, items in menu.items():
        menu_text_lines.append(f"【{category}】")
        for item, price in items.items():
            menu_text_lines.append(f"  {item}: {price} 元")
    menu_text = "\n".join(menu_text_lines)
    await interaction.response.send_message(f"**菜單**:\n{menu_text}", ephemeral=True)

@bot.tree.command(name="評價", description="雙層評價：先選擇類別，再多選食物並輸入評分 (1~5)，累積後可確認或刪除")
async def rate_command(interaction: discord.Interaction):
    view = RatingCategoryView(menu)
    await interaction.response.send_message("請先選擇要評價的料理類別：", view=view, ephemeral=True)

# 不需要輸即推薦
@bot.tree.command(name="推薦", description="使用SDV++模型自動推薦您可能喜歡的餐點")
async def personal_recommend_command(interaction: discord.Interaction):
    recs = get_recommendations(interaction.user.id, top_n=3)
    if isinstance(recs, str):
        await interaction.response.send_message(recs, ephemeral=True)
        return
    rec_lines = []
    for food, score in recs:
        rec_lines.append(f"{food}（預估分數：{score:.2f}）")
    rec_message = "根據您的歷史評分，我們推薦您嘗試：\n" + "\n".join(rec_lines)
    await interaction.response.send_message(rec_message, ephemeral=True)

@bot.tree.command(name="套餐推薦選擇", description="雙層套餐推薦：依類別選擇累積套餐品項，返回與刪除皆可使用")
async def package_recommend_command2(interaction: discord.Interaction):
    view = PackageSelectionView(menu)
    await interaction.response.send_message("請先選擇套餐類別：", view=view, ephemeral=True)

from discord.ext import commands

def flatten_menu(menu):
    flat_list = []
    for category, items in menu.items():
        for item_name, price in items.items():
            flat_list.append((category, item_name, price))
    return flat_list

flat_menu = flatten_menu(menu)

# 利用 difflib 進行模糊比對
def match_food(food_entity, flat_menu, cutoff=0.6):
    # 從扁平化菜單中取出所有品項名稱
    item_names = [item[1] for item in flat_menu]
    matches = difflib.get_close_matches(food_entity, item_names, n=1, cutoff=cutoff)
    if matches:
        best_match_name = matches[0]
    else:
        # 若無符合的，遍歷所有項目並找出最高相似度的項目
        best_ratio = 0
        best_match_name = None
        for item in item_names:
            ratio = difflib.SequenceMatcher(None, food_entity, item).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match_name = item
    # 找出對應的品項、類別及價格
    for category, item_name, price in flat_menu:
        if item_name == best_match_name:
            return (category, item_name, price)
    return None
def convert_quantity(q_text):
    mapping = {
        "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4,
        "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10
    }
    try:
        return int(q_text)
    except ValueError:
        return mapping.get(q_text, 1)


def extract_order_dict(doc, flat_menu):
    order_dict = {}
    current_quantity = None
    for ent in doc.ents:
        if ent.label_ == "QUANTITY":
            current_quantity = convert_quantity(ent.text)
        elif ent.label_ == "FOOD":
            qty = current_quantity if current_quantity is not None else 1
            match_result = match_food(ent.text, flat_menu)
            if match_result:
                # 使用比對到的菜單品項作為 key
                category, canonical_name, price = match_result
                order_dict[canonical_name] = order_dict.get(canonical_name, 0) + qty
            else:
                #未匹配到
                order_dict[ent.text] = order_dict.get(ent.text, 0) + qty
            current_quantity = None
    return order_dict


def format_packages(packages):
    formatted_list = []
    for idx, pkg in enumerate(packages, start=1):
        total_price = pkg['total_price']
        items = []
        has_discount_code = any(package_code.isdigit() for package_code in pkg['packages'])  # 檢查是否有優惠代碼
        
        for package_code, value in pkg['packages'].items():
            if package_code.isdigit():
                items.append(f"優惠代碼 {package_code}:")
            else:
                items.append(f"{package_code}:")
            
            for item in value:
                for item_name, quantity in item.items():
                    items.append(f"    {item_name}: {quantity}")
        package_type = "單點" if idx == 1 and not has_discount_code else f"方案 {idx}"
        
        formatted_list.append(f"{package_type} - 總價: {total_price}元\n" + "\n".join(items))
    
    return "\n\n".join(formatted_list)

@bot.command(name="ner")
async def ner(ctx, *, text: str):
    doc = nlp(text)
    order_dict = extract_order_dict(doc, flat_menu)
    print(order_dict)
    recommended_packages = coupon_recommende.coupon_recommender(order_dict)
    print(recommended_packages)
    formatted_text = format_packages(recommended_packages)
    await ctx.send(f"{formatted_text}")
    await ctx.send(f"訂單: {order_dict}")

if __name__ == "__main__":
    bot.run(config.TOKEN)