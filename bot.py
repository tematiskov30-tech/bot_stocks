# -*- coding: utf-8 -*-
"""
БОТ ДЛЯ УЧЕТА ЗАПАСОВ - ВЕРСИЯ ДЛЯ python-telegram-bot 22.x
"""

import os
import sqlite3
import logging
from datetime import datetime
from collections import defaultdict

# УКАЖИТЕ ВАШ ТОКЕН ЗДЕСЬ!
TOKEN = "8212022181:AAHIRzJzO_ueE-fsOalmVBKkKNFTjKJWimM"  # ⬅️ ЗАМЕНИТЕ НА СВОЙ!
# ==================== КОНСТАНТЫ ДЛЯ НАСТОЕК ====================
TINCTURE_MIN_QUANTITY = 5  # Минимум для настоек
TINCTURE_DAYS_TO_PREPARE = 14  # Дней на настаивание

# Проверка токена
if not TOKEN or TOKEN.startswith("6123456789"):
    print("❌" * 50)
    print("ОШИБКА: Укажите свой токен от @BotFather!")
    print("❌" * 50)
    exit(1)

# Импорты для версии 22.x
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== СОСТОЯНИЯ ====================
SELECT_CATEGORY_ADD, ENTER_PRODUCTS_ADD = range(2)
SELECT_CATEGORY_REMOVE, ENTER_PRODUCTS_REMOVE = range(2, 4)  # Эти состояния больше не используются, но оставим для совместимости
CLEAR_SELECT, CLEAR_CONFIRM = range(4, 6)

# ==================== БАЗА ДАННЫХ ====================

def init_database():
    """Создаем таблицы если их нет"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    
    # Таблица заготовок
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS preparations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        min_quantity INTEGER DEFAULT 5,
        current_quantity REAL DEFAULT 0,
        category TEXT DEFAULT 'Заготовки'
    )
    ''')
    
    # Таблица настоек
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tinctures (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        min_quantity INTEGER DEFAULT 3,
        current_quantity REAL DEFAULT 0,
        category TEXT DEFAULT 'Настойки'
    )
    ''')
    
    # Таблица истории
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        operation TEXT NOT NULL,
        amount REAL NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Таблица шаблонов для заготовок
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS prep_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        min_quantity REAL DEFAULT 5,
        keywords TEXT NOT NULL  -- Ключевые слова через запятую
    )
    ''')
    
    # Таблица шаблонов для настоек
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tincture_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        min_quantity REAL DEFAULT 3,
        keywords TEXT NOT NULL  -- Ключевые слова через запятую
    )
    ''')
    
    # Добавляем базовые шаблоны для заготовок с несколькими ключевыми словами
    prep_templates = [
        ('Содовая на Улуне', 2, 'содовая улун, улун содовая, газява улун, содовая на улуне'),
        ('Содовая', 5, 'содовая, газява, газировка'),
        ('Огурец-Тимьян', 3, 'огур, огурец, тимьян, огурец тимьян'),
        ('Манго-гречишный чай', 3, 'гречишн, манго гречишный, гречишный чай, манго чай'),
        ('Облепиха-апельсин', 3, 'облепиха, апельсин, облепиха апельсин'),
        ('Сироп Мандарин', 1, 'мандарин, сироп мандарин'),
        ('Сироп Мёд', 1, 'мёд, мед, сироп мёд'),
        ('Сироп Улун', 1, 'сироп улун'),
        ('Сироп Вишнёвый', 2, 'вишня, вишневый, сироп вишня, вишнёвый'),
        ('Кордиал Эрл-грей', 2, 'эрл грей, эрл-грей'),
        ('Кордиал Морковь', 2, 'морковь'),
        ('Кордиал Улун', 2, 'кордиал улун'),
        ('Водка на базилике', 2, 'базилик, водка базилик'),
        ('Сахарный сироп', 3, 'сахар, симпл'),
        ('Фреш', 3, 'фреш, лимон сок, цитрус'),
        ('Соус Манго-чили', 0.5, 'чили, манго чили'),
        ('Клубничный шраб', 2, 'клубника, клубничный'),
        ('Грушевый шраб', 2, 'грушевый'),
        ('Ликер Шоколад-кунжут', 2, 'шоколад кунжут, кунжут, шоколад, ликер'),
        ('Джин на белом грибе', 2, 'гриб, джин белый, белый гриб'),
        ('Мэри Микс', 2, 'микс, мэри, мери микс'),
        ('Солёный мёд', 1, 'солёный мёд, солёный мед, соленый мёд, соленый мед'),
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO prep_templates 
        (full_name, min_quantity, keywords)
        VALUES (?, ?, ?)
    ''', prep_templates)
    
    # Добавляем базовые шаблоны для настоек
    tincture_templates = [
        ('Темный ром на изюме', TINCTURE_MIN_QUANTITY, 'ром изюм, темный ром изюм, ром на изюме, изюм'),
        ('Виски на финиках', TINCTURE_MIN_QUANTITY, 'виски финики, финики виски, виски на финиках, финики'),
        ('Виски на вишне', TINCTURE_MIN_QUANTITY, 'виски вишня, вишня виски, виски на вишне, вишня'),
        ('Белый ром на банане и эрл грее', TINCTURE_MIN_QUANTITY, 'белый ром банан, ром банан, ром эрл грей, банан эрл грей, банан'),
        ('Темный ром на кунжуте и какао-бобах', TINCTURE_MIN_QUANTITY, 'ром кунжут, ром какао, темный ром кунжут, какао бобы, бобы, кунжут'),
        ('Виски на печеных яблоках и специях', TINCTURE_MIN_QUANTITY, 'виски яблоки, печеные яблоки, виски специи, яблоки специи'),
        ('Виски на кураге и цедре апельсина', TINCTURE_MIN_QUANTITY, 'виски курага, курага апельсин, цедра апельсина, виски апельсин, курага цедра'),
        ('Виски на маке и яблоках', TINCTURE_MIN_QUANTITY, 'виски мак, мак яблок, виски мак яблок'),
        ('Джин на малине и тимьяне', TINCTURE_MIN_QUANTITY, 'джин малина, малина тимьян, джин тимьян'),
        ('Джин на облепихе и молочном улуне', TINCTURE_MIN_QUANTITY, 'джин облепиха, облепиха улун, молочный улун, облепиха'),
        ('Водка на мандарине', TINCTURE_MIN_QUANTITY, 'водка мандарин, мандарин водка, мандарин'),
        ('Джин на клюкве', TINCTURE_MIN_QUANTITY, 'джин клюква, клюква джин, клюква'),
        ('Джин на груше и цедре лайма', TINCTURE_MIN_QUANTITY, 'джин груша, груша лайм, цедра лайма, груша цедра'),
        ('Виски на бруснике', TINCTURE_MIN_QUANTITY, 'виски брусника, брусника виски, брусника'),
        ('Овсяная лимончелло', TINCTURE_MIN_QUANTITY, 'овсяная лимончелл, лимончелл, овсяная, овсянка лимончелл, овсянка'),
        ('Водка на апельсине и йогурте', TINCTURE_MIN_QUANTITY, 'водка апельсин йогурт, апельсин йогурт, йогурт, водка апельсин'),
        ('Водка на гречке и чили', TINCTURE_MIN_QUANTITY, 'водка гречка чили, гречка чили'),
        ('Водка на свекле и халапеньо', TINCTURE_MIN_QUANTITY, 'водка свекла халапеньо, свекл халапеньо'),
        ('Водка на грейпфруте и гибискусе', TINCTURE_MIN_QUANTITY, 'водка грейпфрут гибискус, грейпфрут гибискус, грейп, гибискус'),
        ('Водка на рукколе и томатах', TINCTURE_MIN_QUANTITY, 'водка руккола томаты, руккола томаты, руккол, томат'),
        ('Водка на болгарском и чили перцах', TINCTURE_MIN_QUANTITY, 'водка болгарский перец, болгарский перец чили, перцы водка, перец, болг, чили'),
        ('Виски на черносливе', TINCTURE_MIN_QUANTITY, 'виски чернослив, чернослив виски, чернослив'),
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO tincture_templates 
        (full_name, min_quantity, keywords)
        VALUES (?, ?, ?)
    ''', tincture_templates)
    
    conn.commit()
    conn.close()
    print("✅ База данных готова!")

init_database()

# ==================== ФУНКЦИИ ДЛЯ ШАБЛОНОВ ====================
def format_float(value):
    """Форматирует float значение до 3 знаков после запятой"""
    if value is None:
        return "0.000"
    try:
        # Округляем до 3 знаков после запятой
        return f"{float(value):.3f}".rstrip('0').rstrip('.') if '.' in f"{float(value):.3f}" else f"{float(value):.3f}"
    except (ValueError, TypeError):
        return str(value)

def find_template_for_product(product_name: str, category: str):
    """
    Ищет шаблон для продукта по ключевым словам
    Возвращает шаблон или None
    """
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    
    # Выбираем нужную таблицу шаблонов
    table_name = 'prep_templates' if category == 'Заготовки' else 'tincture_templates'
    
    cursor.execute(f'''
        SELECT full_name, min_quantity, keywords 
        FROM {table_name}
    ''')
    
    all_templates = cursor.fetchall()
    conn.close()
    
    # Приводим к нижнему регистру для поиска
    product_lower = product_name.lower()
    
    # Ищем совпадение ключа в названии продукта
    for full_name, min_qty, keywords in all_templates:
        # Разделяем ключевые слова по запятой
        keyword_list = [k.strip().lower() for k in keywords.split(',')]
        
        # Проверяем каждое ключевое слово
        for keyword in keyword_list:
            if keyword and keyword in product_lower:
                return {
                    'full_name': full_name,
                    'min_quantity': min_qty,
                    'matched_keywords': keyword_list,
                    'matched_keyword': keyword
                }
    
    return None

# ==================== КЛАВИАТУРЫ ====================

def get_main_keyboard():
    """Создает основную клавиатуру"""
    keyboard = [
        ["🍾Считаемся, брат", "📝В итоге"],
        ["📋План заготовок", "🕯Удалить список"],
        ["❓Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_category_keyboard_add():
    """Клавиатура выбора категории для добавления"""
    keyboard = [
        ["Заготовки", "Настойки"],
        ["Уфф, закончил"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_clear_keyboard():
    """Клавиатура для очистки"""
    keyboard = [
        ["❌ ВСЁ УДАЛИТЬ", "🚫 Только выбранное"],
        ["🔙 Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_confirm_keyboard():
    """Клавиатура для подтверждения"""
    keyboard = [
        ["🔥 ДА, УДАЛИТЬ!", "🙅‍♂️ НЕТ, ОТМЕНА!"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== ФУНКЦИИ БАЗЫ ДАННЫХ ====================

def add_product(product_name, amount, category='Заготовки'):
    """Добавляет продукт в базу с автоматическим применением шаблона"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    
    try:
        # 1. Определяем таблицу
        table_name = 'preparations' if category == 'Заготовки' else 'tinctures'
        
        # 2. Ищем шаблон для этого продукта
        template = find_template_for_product(product_name, category)
        
        if template:
            # Используем данные из шаблона
            final_name = template['full_name']
            min_quantity = template['min_quantity']
            used_template = True
        else:
            # Шаблон не найден - используем введенные данные
            final_name = product_name.title()
            min_quantity = 1 if category == 'Заготовки' else 3
            used_template = False
        
        # 3. Ищем существующий продукт
        cursor.execute(
            f"SELECT id, current_quantity FROM {table_name} WHERE LOWER(name)=LOWER(?)",
            (final_name,)
        )
        result = cursor.fetchone()
        
        if result:
            # Обновляем существующий продукт
            product_id, current = result
            new_quantity = current + amount
            
            cursor.execute(
                f"UPDATE {table_name} SET current_quantity=?, min_quantity=? WHERE id=?",
                (new_quantity, min_quantity, product_id)
            )
        else:
            # Создаем новый продукт
            cursor.execute(
                f"INSERT INTO {table_name} (name, current_quantity, min_quantity, category) VALUES (?, ?, ?, ?)",
                (final_name, amount, min_quantity, category)
            )
            new_quantity = amount
            product_id = cursor.lastrowid
        
        # 4. Добавляем в историю
        cursor.execute(
            "INSERT INTO history (product_name, category, operation, amount) VALUES (?, ?, 'add', ?)",
            (final_name, category, amount)
        )
        
        conn.commit()
        
        return {
            'success': True,
            'quantity': new_quantity,
            'product_name': final_name,
            'min_quantity': min_quantity,
            'category': category,
            'used_template': used_template,
        }
        
    except Exception as e:
        print(f"❌ Ошибка добавления: {e}")
        return {'success': False, 'error': str(e)}
    finally:
        conn.close()

def batch_add_products(product_list, category='Заготовки'):
    """Добавляет несколько продуктов сразу"""
    results = []
    errors = []
    
    for product_data in product_list:
        try:
            product_name = product_data.get('name', '')
            amount = product_data.get('amount', 0)
            
            if not product_name or amount <= 0:
                continue
            
            result = add_product(product_name, amount, category)
            
            if result['success']:
                results.append(result)
            else:
                errors.append(f"{product_name}: {result['error']}")
                
        except Exception:
            continue
    
    return results, errors

def parse_product_line(line):
    """Парсит строку с продуктом (без единиц измерения)"""
    line = line.strip()
    if not line:
        return None
    
    parts = line.split()
    if len(parts) < 2:
        return None
    
    product_name = ''
    amount = 0
    
    # Пробуем найти число в конце
    try:
        # Проверяем последнюю часть - это число?
        amount_str = parts[-1].replace(',', '.')
        amount = float(amount_str)
        product_name = ' '.join(parts[:-1])
    except ValueError:
        # Если последняя часть не число, ищем число в строке
        for i in range(len(parts)-1, -1, -1):
            try:
                amount_str = parts[i].replace(',', '.')
                amount = float(amount_str)
                product_name = ' '.join(parts[:i])
                break
            except ValueError:
                continue
    
    if not product_name or amount <= 0:
        return None
    
    return {
        'name': product_name,
        'amount': amount
    }

def is_batch_input(text):
    """Определяет, является ли ввод пакетным (несколько строк)"""
    lines = text.strip().split('\n')
    return len(lines) > 1

def parse_batch_input(text):
    """Парсит пакетный ввод"""
    lines = text.strip().split('\n')
    products = []
    
    for line in lines:
        if line.strip():
            product_data = parse_product_line(line)
            if product_data:
                products.append(product_data)
    
    return products

def get_all_products():
    """Получает ВСЕ продукты из обеих категорий"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT name, current_quantity, min_quantity, 'Заготовки' as category FROM preparations ORDER BY name")
    preparations = cursor.fetchall()
    
    cursor.execute("SELECT name, current_quantity, min_quantity, 'Настойки' as category FROM tinctures ORDER BY name")
    tinctures = cursor.fetchall()
    
    conn.close()
    
    all_products = preparations + tinctures
    return all_products

def get_low_stock_sorted():
    """Получает продукты с низким остатком, сортирует по проценту остатка"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    
    # Получаем заготовки с низким остатком
    cursor.execute(
        "SELECT name, current_quantity, min_quantity, 'Заготовки' as category FROM preparations WHERE current_quantity <= min_quantity"
    )
    low_preparations = cursor.fetchall()
    
    # Получаем настойки с низким остатком
    cursor.execute(
        "SELECT name, current_quantity, ?, 'Настойки' as category FROM tinctures WHERE current_quantity <= ?",
        (TINCTURE_MIN_QUANTITY, TINCTURE_MIN_QUANTITY)
    )
    low_tinctures = cursor.fetchall()
    
    conn.close()
    
    # Объединяем и сортируем по проценту от минимума (чем меньше, тем выше)
    all_low = low_preparations + low_tinctures
    
    # Сортируем по проценту остатка (от меньшего к большему)
    all_low_sorted = sorted(all_low, key=lambda x: (x[1] / x[2]) if x[2] > 0 else 0)
    
    return all_low_sorted

def clear_all_products():
    """Удаляет ВСЕ продукты из обеих таблиц"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    
    try:
        # Получаем количество перед удалением
        cursor.execute("SELECT COUNT(*) FROM preparations")
        prep_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tinctures")
        tincture_count = cursor.fetchone()[0]
        
        total_count = prep_count + tincture_count
        
        # Удаляем все продукты
        cursor.execute("DELETE FROM preparations")
        cursor.execute("DELETE FROM tinctures")
        
        # Добавляем запись в историю
        if total_count > 0:
            cursor.execute(
                "INSERT INTO history (product_name, category, operation, amount) VALUES (?, 'Обе категории', 'clear_all', ?)",
                ('ВСЕ ПРОДУКТЫ', total_count)
            )
        
        conn.commit()
        return True, f"✅ Удалено {total_count} позиций. Список пуст! Не забудь, пожалуйста, теперь составить новый))"
        
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}"
    finally:
        conn.close()

def clear_selected_product(product_name, category):
    """Удаляет конкретный продукт из указанной категории"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    
    try:
        # Определяем таблицу
        table_name = 'preparations' if category == 'Заготовки' else 'tinctures'
        
        # Ищем продукт
        cursor.execute(
            f"SELECT id, current_quantity FROM {table_name} WHERE LOWER(name)=LOWER(?)",
            (product_name,)
        )
        result = cursor.fetchone()
        
        if not result:
            return False, f"Продукт '{product_name}' не найден!"
        
        product_id, quantity = result
        
        # Удаляем продукт
        cursor.execute(f"DELETE FROM {table_name} WHERE id=?", (product_id,))
        
        # Добавляем в историю
        cursor.execute(
            "INSERT INTO history (product_name, category, operation, amount) VALUES (?, ?, 'delete_product', ?)",
            (product_name, category, quantity)
        )
        
        conn.commit()
        return True, f"Выпито: {product_name} ({format_float(quantity)} л)"
        
    except Exception as e:
        return False, f"❌ Ошибка: {str(e)}"
    finally:
        conn.close()

# ==================== ОБРАБОТЧИКИ ДОБАВЛЕНИЯ ====================

async def start_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления"""
    await update.message.reply_text(
        "📝 *С чего начнём?*\n\n"
        "Выбери категорию или тяжело вздохни и сделай вид что работал, а затем тыкай последнюю кнопку)",
        parse_mode='Markdown',
        reply_markup=get_category_keyboard_add()
    )
    
    context.user_data['operation'] = 'add'
    return SELECT_CATEGORY_ADD

async def select_category_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выбора категории для добавления"""
    text = update.message.text
    
    if text == "Уфф, закончил":
        await update.message.reply_text(
            "Отдыхай...",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    elif text == "Заготовки":
        category = "Заготовки"
        
        await update.message.reply_text(
            f"Ну че там насчитал, математик?",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([["Уфф, закончил"]], resize_keyboard=True)
        )
        
        context.user_data['category'] = category
        return ENTER_PRODUCTS_ADD
        
    elif text == "Настойки":
        category = "Настойки"
        
        await update.message.reply_text(
            "Да ладно тебе, я настаиваю",
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([["Уфф, закончил"]], resize_keyboard=True)
        )
        
        context.user_data['category'] = category
        return ENTER_PRODUCTS_ADD
    
    else:
        await update.message.reply_text(
            "Пожалуйста, выбери категорию или нажми 'Уфф, закончил':",
            reply_markup=get_category_keyboard_add()
        )
        return SELECT_CATEGORY_ADD

async def enter_products_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ввода продуктов для добавления"""
    text = update.message.text.strip()
    
    # Получаем сохраненные данные
    category = context.user_data.get('category', 'Заготовки')
    
    # Проверяем завершение
    if text == "Уфф, закончил":
        await update.message.reply_text(
            "У меня как у первокурсницы - всё записано✅",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    try:
        # Определяем тип ввода
        if is_batch_input(text):
            # Пакетный ввод
            products = parse_batch_input(text)
            
            if products:
                results, errors = batch_add_products(products, category)
                
                success_count = len(results)
                
                if success_count > 0:
                    # Собираем сообщение о результатах
                    message = f"✅ *Добавлено {success_count} позиций:*\n\n"
                    for i, res in enumerate(results[:5], 1):
                        message += f"{i}. *{res['product_name']}*: +{format_float(res['quantity'])} л\n"
                    
                    if len(results) > 5:
                        message += f"...и еще {len(results) - 5}\n"
                    
                    if errors:
                        message += f"\n❌ *Ошибки ({len(errors)}):*\n"
                        for error in errors[:3]:
                            message += f"• {error}\n"
                        if len(errors) > 3:
                            message += f"...и еще {len(errors) - 3}\n"
                    
                    await update.message.reply_text(
                        message,
                        parse_mode='Markdown',
                        reply_markup=ReplyKeyboardMarkup([["Уфф, закончил"]], resize_keyboard=True)
                    )
                else:
                    await update.message.reply_text(
                        "❌ Не получилось добавить. Попробуй снова:",
                        reply_markup=ReplyKeyboardMarkup([["Уфф, закончил"]], resize_keyboard=True)
                    )
            else:
                await update.message.reply_text(
                    "❌ Не понял формат. Пиши так: Название Количество\nПопробуй снова:",
                    reply_markup=ReplyKeyboardMarkup([["Уфф, закончил"]], resize_keyboard=True)
                )
            
            return ENTER_PRODUCTS_ADD
            
        else:
            # Одиночный ввод
            product_data = parse_product_line(text)
            
            if product_data:
                result = add_product(product_data['name'], product_data['amount'], category)
                
                if result['success']:
                    # Формируем сообщение
                    if result['used_template']:
                        message = f"✅ *{result['product_name']}*: +{format_float(product_data['amount'])} л"
                    else:
                        message = f"✅ *{result['product_name']}*: +{format_float(product_data['amount'])} л"
                    
                    await update.message.reply_text(
                        message,
                        parse_mode='Markdown',
                        reply_markup=ReplyKeyboardMarkup([["Уфф, закончил"]], resize_keyboard=True)
                    )
                else:
                    await update.message.reply_text(
                        f"❌ Ошибка: {result['error']}\nПопробуй снова:",
                        reply_markup=ReplyKeyboardMarkup([["Уфф, закончил"]], resize_keyboard=True)
                    )
            else:
                await update.message.reply_text(
                    "❌ Не понял формат. Пиши так: Название Количество\nПопробуй снова:",
                    reply_markup=ReplyKeyboardMarkup([["Уфф, закончил"]], resize_keyboard=True)
                )
            
            return ENTER_PRODUCTS_ADD
    
    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка обработки. Попробуй снова:",
            reply_markup=ReplyKeyboardMarkup([["Уфф, закончил"]], resize_keyboard=True)
        )
        return ENTER_PRODUCTS_ADD

# ==================== ОБРАБОТЧИКИ ОЧИСТКИ ====================

async def clear_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало очистки"""
    await update.message.reply_text(
        "🧹 *ОЧИСТКА СПИСКА*\n\n"
        "Выбери действие:",
        parse_mode='Markdown',
        reply_markup=get_clear_keyboard()
    )
    return CLEAR_SELECT

async def clear_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор типа очистки"""
    text = update.message.text
    
    if text == "🔙 Назад":
        await update.message.reply_text(
            "✅ Очистка отменена",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    elif text == "❌ ВСЁ УДАЛИТЬ":
        all_products = get_all_products()
        count = len(all_products)
        
        if count == 0:
            await update.message.reply_text(
                "📭 Список и так пуст!",
                reply_markup=get_main_keyboard()
            )
            return ConversationHandler.END
        
        await update.message.reply_text(
            f"🔥 *ВНИМАНИЕ!*\n\n"
            f"Ты собираешься удалить *ВСЕ {count} позиций*!\n\n"
            f"Это действие *НЕЛЬЗЯ отменить*!\n"
            f"Ты уверен?",
            parse_mode='Markdown',
            reply_markup=get_confirm_keyboard()
        )
        context.user_data['clear_type'] = 'all'
        return CLEAR_CONFIRM
    
    elif text == "🚫 Только выбранное":
        all_products = get_all_products()
        
        if not all_products:
            await update.message.reply_text(
                "📭 Список пуст! Нечего удалять.",
                reply_markup=get_main_keyboard()
            )
            return ConversationHandler.END
        
        # Группируем по категориям
        preparations = [p for p in all_products if p[3] == 'Заготовки']
        tinctures = [p for p in all_products if p[3] == 'Настойки']
        
        message = "📋 *Выбери продукт для удаления:*\n\n"
        
        if preparations:
            message += "🥫 *ЗАГОТОВКИ:*\n"
            for i, (name, qty, min_qty, _) in enumerate(preparations, 1):
                message += f"{i}. {name} ({format_float(qty)} л)\n"
            message += "\n"
        
        if tinctures:
            message += "🍶 *НАСТОЙКИ:*\n"
            for i, (name, qty, min_qty, _) in enumerate(tinctures, len(preparations) + 1):
                message += f"{i}. {name} ({format_float(qty)} л)\n"
        
        message += "\nВведи номер продукта или его название:"
        
        context.user_data['clear_type'] = 'selected'
        context.user_data['all_products'] = all_products
        
        await update.message.reply_text(
            message,
            parse_mode='Markdown',
            reply_markup=ReplyKeyboardMarkup([["🔙 Назад"]], resize_keyboard=True)
        )
        return CLEAR_CONFIRM
    
    return CLEAR_SELECT

async def clear_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подтверждение очистки"""
    text = update.message.text
    
    if text == "🙅‍♂️ НЕТ, ОТМЕНА!" or text == "🔙 Назад":
        await update.message.reply_text(
            "✅ Очистка отменена",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END
    
    elif text == "🔥 ДА, УДАЛИТЬ!":
        clear_type = context.user_data.get('clear_type')
        
        if clear_type == 'all':
            success, message = clear_all_products()
            await update.message.reply_text(
                message,
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
            return ConversationHandler.END
    
    else:
        # Пользователь ввел номер или название продукта
        clear_type = context.user_data.get('clear_type')
        
        if clear_type == 'selected':
            all_products = context.user_data.get('all_products', [])
            
            if not all_products:
                await update.message.reply_text(
                    "❌ Список продуктов пуст",
                    reply_markup=get_main_keyboard()
                )
                return ConversationHandler.END
            
            # Пробуем понять что ввел пользователь
            input_text = text.strip()
            selected_product = None
            selected_category = None
            
            # Пробуем номер
            if input_text.isdigit():
                index = int(input_text) - 1
                if 0 <= index < len(all_products):
                    selected_product = all_products[index][0]
                    selected_category = all_products[index][3]
            
            # Если не номер, ищем по названию
            if not selected_product:
                for name, _, _, category in all_products:
                    if name.lower() == input_text.lower():
                        selected_product = name
                        selected_category = category
                        break
            
            if selected_product and selected_category:
                success, message = clear_selected_product(selected_product, selected_category)
                await update.message.reply_text(
                    message,
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard()
                )
            else:
                await update.message.reply_text(
                    f"❌ Продукт '{input_text}' не найден!",
                    reply_markup=get_main_keyboard()
                )
            
            return ConversationHandler.END
    
    return CLEAR_CONFIRM

# ==================== КОМАНДА "ИТОГО" ====================

async def total_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает полный список всего, что есть"""
    all_products = get_all_products()
    
    if not all_products:
        await update.message.reply_text("📭 Список пуст! Пора что-то заготовить.")
        return
    
    # Разделяем по категориям
    preparations = [p for p in all_products if p[3] == 'Заготовки']
    tinctures = [p for p in all_products if p[3] == 'Настойки']
    
    # ПОЛНЫЙ СПИСОК
    message = "📊 *ИТОГО - ВСЁ ЧТО ЕСТЬ:*\n\n"
    
    if preparations:
        message += "*ЗАГОТОВКИ:*\n"
        for name, qty, min_qty, _ in preparations:
            status = "⚠️" if qty <= min_qty else "✅"
            message += f"{status} *{name}*  {format_float(qty)} л\n"
    
    if tinctures:
        message += "\n*НАСТОЙКИ:*\n"
        for name, qty, min_qty, _ in tinctures:
            # Для настоек используем особый минимум
            status = "⚠️" if qty <= TINCTURE_MIN_QUANTITY else "✅"
            message += f"{status} *{name}* {format_float(qty)} л\n"
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())

# ==================== КОМАНДА "ПЛАН ЗАГОТОВОК" ====================

async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает план заготовок и настоек (что нужно сделать)"""
    from datetime import datetime, timedelta
    
    low_products = get_low_stock_sorted()
    
    if not low_products:
        await update.message.reply_text(
            "✅ *ВСЁ ЗАЕБИСЬ!*\n\n"
            "Все минимумы соблюдены, можно расслабиться. 🍻",
            parse_mode='Markdown',
            reply_markup=get_main_keyboard()
        )
        return
    
    # Расчет даты готовности
    today = datetime.now()
    ready_date = today + timedelta(days=TINCTURE_DAYS_TO_PREPARE)
    ready_date_str = ready_date.strftime("%d.%m.%Y")
    
    # Сначала обычные заготовки
    low_preps = [p for p in low_products if p[3] == 'Заготовки']
    low_tincts = [p for p in low_products if p[3] == 'Настойки']
    
    plan_message = "📋 *ПЛАН ЗАГОТОВОК:*\n\n"
    has_content = False
    
    # Заготовки
    if low_preps:
        plan_message += "*Если нечем заняться, делай:*\n\n"
        for i, (name, qty, min_qty, category) in enumerate(low_preps, 1):
            need = max(0, min_qty - qty)
            if need > 0:
                plan_message += f"*→ {name}* - {format_float(need)} л\n"
                has_content = True
        
        plan_message += "\n"
    
    # Настойки
    if low_tincts:
        plan_message += f"*НАСТОЙКИ, которые пора заряжать или цедить (если ставишь сегодня, готово {ready_date_str}):*\n\n"
        for i, (name, qty, min_qty, category) in enumerate(low_tincts, 1):
            need = max(0, TINCTURE_MIN_QUANTITY - qty)
            if need > 0:
                plan_message += f"→ *{name}*\n"
                has_content = True
    
    if not has_content:
        plan_message = "✅ *ВСЁ ЗАЕБИСЬ!*\n\nВсе минимумы соблюдены, можно расслабиться. 🍻"
    
    await update.message.reply_text(plan_message, parse_mode='Markdown', reply_markup=get_main_keyboard())

# ==================== ОСНОВНЫЕ КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"🤘Привет, {user.first_name}, братское сердце!\n"
        f"Я бро для инвентаризации заготовок и настоек.\n\n"
        f"Итак, как это работает: \n\n"
        f"    У всех пользователей бота один список заготовок. Поэтому очень удобно отслеживать актуальные остатки)) \n"
        f"    ''Настойки'' и ''заготовки'' -  это разные категории для этого бота.  Настойки - все, что в баночках по две недели на згц стоит. Су-ви заготовки вроде ''Джина на базилике'' не считаются настойкой - такая у них судьба.\n\n"
        f"Че тыкать-то???\n\n"
        f"    1. Нажми ''Считаемся, брат'' для добавления заготовок в список.\n\n"
        f"    2. Выбери категорию: настойки или заготовки.\n\n"
        f"    3. **Формат ввода**: Название количество\n\n"
        f"    Пример твоего сообщения:\n\n"
        f"        Текила 3\n\n"
        f"    Можешь отправлять как одиночными сообщениями, так и сразу списком через энтер.\n\n"
        f"    Пример твоего сообщения:\n\n"
        f"        Огурец тимьян 4\n"
        f"        Манго чили 1.2\n"
        f"        Грушевый шраб 0.3\n"
        f"        ...\n"
        f"        Мери Микс 3\n\n"
        f"    Над написанием вообще не парься, я тебя пойму, а если нет, то пиши сюда - @pleasestopitmommy\n\n"
        f"    4. Закончил? Тыкай на кнопку в меню и тебя вернет на главную!\n\n"
        f"    5. Нажми ''В итоге'' чтобы увидеть весь список заготовок.\n\n"
        f"    6. Нажми ''План заготовок'' чтобы узнать, что нужно срочно сделать.\n\n"
        f"    7. Кнопку ''Очистить список'' используй когда полностью пересчитываешь заготовки, потому что список удаляется у всех.\n\n"
        f"    8. ''Помощь'' - короткая справка про кнопки",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
📚 *КАК РАБОТАТЬ:*

1. 🍾 *Считаемся, брат* - добавить остатки
   → Выбери категорию (Заготовки/Настойки)
   → Просто пиши: Название Количество
   → Можно списком через Enter
   → Жми 'Уфф, закончил' когда закончил

2. 📊 *В итоге* - показывает:
   → Полный список всего что есть

3. 📋 *План заготовок* - показывает:
   → Что нужно срочно сделать (где остатки ниже минимума)

4. 🧹 *Очистить список* - удалить всё или выбранное

    """
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard())

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик отмены для всех состояний"""
    await update.message.reply_text(
        "✅ Действие отменено",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# ==================== ОБРАБОТКА СООБЩЕНИЙ ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все текстовые сообщения"""
    text = update.message.text.strip()
    
    # Обработка кнопок
    if text == "🍾Считаемся, брат":
        # Эта кнопка обрабатывается ConversationHandler
        return
    
    elif text == "📝В итоге":
        await total_command(update, context)
        return
    
    elif text == "📋План заготовок":
        await plan_command(update, context)
        return
    
    elif text == "🕯Удалить список":
        await clear_start(update, context)
        return
    
    elif text == "❓Помощь":
        await help_command(update, context)
        return
    
    # Если не кнопка, возвращаем на главную
    await update.message.reply_text(
        "Используй кнопки меню для работы с ботом:",
        reply_markup=get_main_keyboard()
    )

# ==================== ЗАПУСК БОТА ====================

def main():
    """Запускает бота"""
    print("=" * 50)
    print("🤖 БОТ ДЛЯ УЧЕТА ЗАПАСОВ И НАСТОЕК")
    print("=" * 50)
    
    if TOKEN.startswith("6123456789"):
        print("❌ ЗАМЕНИТЕ ТОКЕН НА СВОЙ!")
        print("Получите у @BotFather в Telegram")
        return
    
    print(f"✅ Токен: {TOKEN[:15]}...")
    print("✅ База данных готова")
    print("\n👉 Откройте Telegram")
    print("👉 Найдите своего бота")
    print("👉 Напишите /start")
    print("=" * 50)
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    # Создаем ConversationHandler для добавления
    add_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🍾Считаемся, брат$"), start_add)],
        states={
            SELECT_CATEGORY_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_category_add)],
            ENTER_PRODUCTS_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_products_add)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )
    
    # Создаем ConversationHandler для очистки
    clear_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🕯Удалить список$"), clear_start)],
        states={
            CLEAR_SELECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, clear_select)],
            CLEAR_CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, clear_confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )
    
    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    
    # Добавляем ConversationHandler'ы
    app.add_handler(add_conv_handler)
    app.add_handler(clear_conv_handler)
    
    # Обработчик всех текстовых сообщений
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("✅ Бот запущен!")
    print("⏹️ Нажмите Ctrl+C для остановки")
    print("=" * 50)
    
    # Запускаем бота
    app.run_polling()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        input("Нажмите Enter...")

