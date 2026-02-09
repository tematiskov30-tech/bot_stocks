# -*- coding: utf-8 -*-
"""
БОТ ДЛЯ УЧЕТА ЗАПАСОВ - ВЕРСИЯ ДЛЯ python-telegram-bot 22.x
"""

import os
import sqlite3
import logging
from datetime import datetime

# УКАЖИТЕ ВАШ ТОКЕН ЗДЕСЬ!
TOKEN = "8212022181:AAHIRzJzO_ueE-fsOalmVBKkKNFTjKJWimM"  # ⬅️ ЗАМЕНИТЕ НА СВОЙ!

# Проверка токена
if not TOKEN or TOKEN.startswith("6123456789"):
    print("❌" * 50)
    print("ОШИБКА: Укажите свой токен от @BotFather!")
    print("❌" * 50)
    exit(1)

# Импорты для версии 22.x
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

# Настраиваем логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== БАЗА ДАННЫХ ====================

def init_database():
    """Создаем таблицы если их нет"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        unit TEXT DEFAULT 'шт',
        min_quantity INTEGER DEFAULT 5,
        current_quantity REAL DEFAULT 0
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_name TEXT NOT NULL,
        operation TEXT NOT NULL,
        amount REAL NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных готова!")

init_database()

# ==================== КЛАВИАТУРА ====================

def get_main_keyboard():
    """Создает основную клавиатуру"""
    keyboard = [
        ["🍾 Считаемся, брат", "📉 Понял, вычеркиваем"],
        ["📋 Че по остаткам?", "⚠️ Пизда мало"],
        ["🔄 История", "❓ Помощь"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==================== ФУНКЦИИ БАЗЫ ДАННЫХ ====================

def add_product(product_name, amount, unit='шт'):
    """Добавляет продукт в базу"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    
    try:
        # Ищем продукт
        cursor.execute(
            "SELECT id, current_quantity FROM products WHERE LOWER(name)=LOWER(?)",
            (product_name,)
        )
        result = cursor.fetchone()
        
        if result:
            # Обновляем существующий
            product_id, current = result
            new_quantity = current + amount
            cursor.execute(
                "UPDATE products SET current_quantity=? WHERE id=?",
                (new_quantity, product_id)
            )
        else:
            # Добавляем новый
            cursor.execute(
                "INSERT INTO products (name, unit, current_quantity) VALUES (?, ?, ?)",
                (product_name.title(), unit, amount)
            )
            new_quantity = amount
        
        # Добавляем в историю
        cursor.execute(
            "INSERT INTO history (product_name, operation, amount) VALUES (?, 'add', ?)",
            (product_name.title(), amount)
        )
        
        conn.commit()
        return True, new_quantity
        
    except Exception as e:
        print(f"Ошибка добавления: {e}")
        return False, 0
    finally:
        conn.close()

def remove_product(product_name, amount):
    """Списывает продукт"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    
    try:
        # Ищем продукт
        cursor.execute(
            "SELECT id, current_quantity FROM products WHERE LOWER(name)=LOWER(?)",
            (product_name,)
        )
        result = cursor.fetchone()
        
        if not result:
            return False, "Из пустой кастрюли каши не начерпаешь!"
        
        product_id, current = result
        
        if current < amount:
            return False, f"Ты попутал! Есть: {current}"
        
        new_quantity = current - amount
        cursor.execute(
            "UPDATE products SET current_quantity=? WHERE id=?",
            (new_quantity, product_id)
        )
        
        # Добавляем в историю
        cursor.execute(
            "INSERT INTO history (product_name, operation, amount) VALUES (?, 'remove', ?)",
            (product_name.title(), amount)
        )
        
        conn.commit()
        return True, new_quantity
        
    except Exception as e:
        print(f"Ошибка списания: {e}")
        return False, f"Ошибка: {e}"
    finally:
        conn.close()

def get_all_products():
    """Получает все продукты"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, current_quantity, unit, min_quantity FROM products ORDER BY name")
    products = cursor.fetchall()
    conn.close()
    return products

def get_low_stock():
    """Получает продукты с низким остатком"""
    conn = sqlite3.connect('stock.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, current_quantity, min_quantity, unit FROM products WHERE current_quantity <= min_quantity ORDER BY current_quantity"
    )
    products = cursor.fetchall()
    conn.close()
    return products

# ==================== КОМАНДЫ ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    await update.message.reply_text(
        f"🤘Привет, {user.first_name}, братское сердце!\n\n"
        f"Я бро для инвентаризации заготовок.\n"
        f"Ну, там русским по кнопкам написано. Куда жмать разберешься:",
        reply_markup=get_main_keyboard()
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
📚 КАК РАБОТАТЬ:

1. Хуякс, пацаны решили что сегодня именно ты считаешь остатки.

2. Нашёл ЗГЦ? Тыкай "🍾 Считаемся, брат" и строчи остатки в формате:
Название количество единица

3. Проебался? Не беда. Кнопка "📉 Понял, вычеркиваем" - тебе поможет. Жми и списывай сколько влезет, это же не iiko. Формат:
Название количество
(без единицы измерения)

4. 📋Че по остаткам?  - покажет все продукты

5. ⚠️ Пизда мало - покажет, что точно нужно сделать

6. 🔄 История - последние операции

💡 **Можно писать прямо:**
`Мука 5 кг` - добавит 5 кг муки
`Молоко 2` - спишет 2 молока
    """
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard())

async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все продукты"""
    products = get_all_products()
    
    if not products:
        await update.message.reply_text("📭 Список продуктов пуст!")
        return
    
    message = "📋 Че по остаткам?\n\n"
    for name, qty, unit, min_qty in products:
        status = "⚠️" if qty <= min_qty else "✅"
        message += f"{status} *{name}*\n"
        message += f"   В наличии: {qty} {unit}\n"
        message += f"   Минимум: {min_qty} {unit}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())

async def low_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает что заканчивается"""
    products = get_low_stock()
    
    if not products:
        await update.message.reply_text("✅ Все заебись!", reply_markup=get_main_keyboard())
        return
    
    message = "НАДО СВАРГАНИТЬ:\n\n"
    for name, qty, min_qty, unit in products:
        need = min_qty - qty
        if need > 0:
            message += f"⚠️ *{name}*\n"
            message += f"   Осталось: {qty} {unit}\n"
            message += f"   Минимум: {min_qty} {unit}\n"
            message += f"   → Намутить: {need} {unit}\n\n"
    
    await update.message.reply_text(message, parse_mode='Markdown', reply_markup=get_main_keyboard())

# ==================== ОБРАБОТКА СООБЩЕНИЙ ====================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает все текстовые сообщения"""
    text = update.message.text.strip()
    
    # Обработка кнопок
    if text =="🍾 Считаемся, брат":
        await update.message.reply_text(
            "📝 Введи, что посчитал:\n"
            "Формат: *Название Количество Единица*\n\n"
            "Примеры:\n"
            "• Газированный слив 3 л\n"
            "• Водка на базилике 25 л\n"
            "• Фреш 5 л",
            parse_mode='Markdown'
        )
        return
    
    elif text =="📉 Понял, вычеркиваем" :
        await update.message.reply_text(
            "📝 Рассказывай, че убрать:\n"
            "Формат: *Название Количество*\n\n"
            "Примеры:\n"
            "• Фреш 2\n"
            "• Текила 1\n"
            "• Кордил Эрл грей 5",
            parse_mode='Markdown'
        )
        return
    
    elif text =="📋 Че по остаткам?" :
        await list_command(update, context)
        return
    
    elif text == "⚠️ Пизда мало":
        await low_command(update, context)
        return
    
    elif text == "🔄 История":
        await update.message.reply_text("🔄 История операций", reply_markup=get_main_keyboard())
        return
    
    elif text == "❓ Помощь":
        await help_command(update, context)
        return
    
    # Если не кнопка, пробуем распознать как команду добавления/списания
    await process_user_input(update, text)

async def process_user_input(update: Update, text: str):
    """Обрабатывает пользовательский ввод - ИСПРАВЛЕННАЯ ВЕРСИЯ"""
    try:
        parts = text.split()
        
        if len(parts) < 2:
            await update.message.reply_text(
                "❌ Мало слов. Примеры:\n"
                "• `Джин 4 л` - добавить\n"
                "• `Джин 2` - списать",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
            return
        
        # Расширенный список единиц измерения
        units = ['кг', 'г', 'л', 'мл', 'шт', 'банок', 'пачек', 'упаковок', 
                'бутылок', 'литров', 'грамм', 'килограмм', 'литр']
        
        # Определяем операцию
        operation = None
        unit = 'шт'
        amount = None
        product_name = ''
        
        # Вариант 1: Есть единица измерения в конце - это добавление
        if parts[-1].lower() in units:
            operation = 'add'
            unit = parts[-1].lower()
            
            # Пытаемся найти количество
            try:
                amount = float(parts[-2].replace(',', '.'))
                product_name = ' '.join(parts[:-2])
            except ValueError:
                # Если предпоследнее не число, ищем любое число
                for i in range(len(parts)-1, -1, -1):
                    try:
                        amount = float(parts[i].replace(',', '.'))
                        product_name = ' '.join(parts[:i] + parts[i+1:-1])
                        break
                    except:
                        continue
        
        # Вариант 2: Нет единицы - возможно списание
        else:
            operation = 'remove'
            
            # Ищем последнее число
            for i in range(len(parts)-1, -1, -1):
                try:
                    amount = float(parts[i].replace(',', '.'))
                    product_name = ' '.join(parts[:i])
                    break
                except:
                    continue
        
        # Проверяем что всё нашлось
        if not product_name or not amount:
            await update.message.reply_text(
                "❌ Не вижу количество или название!\n"
                "Примеры:\n"
                "• `Джин 4 л` - добавить 4 литра джина\n"
                "• `Джин 2` - списать 2 джина",
                parse_mode='Markdown',
                reply_markup=get_main_keyboard()
            )
            return
        
        # Выполняем операцию
        if operation == 'add':
            success, result = add_product(product_name, amount, unit)
            if success:
                await update.message.reply_text(
                    f"✅ Записал: {product_name.title()}\n"
                    f"📦 Было: +{amount} {unit}\n"
                    f"🏪 Стало: {result} {unit}",
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard()
                )
            else:
                await update.message.reply_text("❌ Ошибка при добавлении")
        
        elif operation == 'remove':
            success, result = remove_product(product_name, amount)
            if success:
                await update.message.reply_text(
                    f"✅ Убрал: {product_name.title()}\n"
                    f"📉 Было: -{amount}\n"
                    f"🏪 Стало: {result}",
                    parse_mode='Markdown',
                    reply_markup=get_main_keyboard()
                )
            else:
                await update.message.reply_text(f"❌ {result}")
    
    except Exception as e:
        print(f"❌ Ошибка в process_user_input: {e}")
        import traceback
        traceback.print_exc()
        
        await update.message.reply_text(
            f"❌ Ошибка обработки.\n"
            f"Попробуйте простой формат:\n"
            f"• `Джин 4 л`\n"
            f"• `Использовал джин 2`",
            reply_markup=get_main_keyboard()
        )

# ==================== ЗАПУСК БОТА ====================

def main():
    """Запускает бота"""
    print("=" * 50)
    print("🤖 БОТ ДЛЯ УЧЕТА ЗАПАСОВ")
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
    
    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("list", list_command))
    app.add_handler(CommandHandler("low", low_command))
    
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
