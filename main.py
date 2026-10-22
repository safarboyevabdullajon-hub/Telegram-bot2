import os
import asyncio
import sqlite3
import gspread
import pandas as pd
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('8888235408:AAHSwEcY435IsSazuVZrx_9ghQm59ss1LW4')
FOLDER_ID = os.getenv('1yuoGv61gwaHb7v-cIimzHcgxsKcEERPx')
ADMIN_ID = "5966398440" 

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Google API ulanishlari
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
gspread_client = gspread.authorize(creds)
drive_service = build('drive', 'v3', credentials=creds)

# SQLite bazasiga ulanish
conn = sqlite3.connect('reports.db', check_same_thread=False)

def get_files_in_folder():
    # Papka ichidagi barcha Google Sheets fayllarini topish
    query = f"'{FOLDER_ID}' in parents and mimeType='application/vnd.google-apps.spreadsheet' and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    return results.get('files', [])

def get_sheet_data(file_id):
    sheet = gspread_client.open_by_key(file_id).sheet1
    data = sheet.get_all_records()
    return pd.DataFrame(data)

def compare_and_save(file_name, current_df):
    table_name = file_name.replace(" ", "_") # Bazada jadval nomi sifatida fayl nomidan foydalanamiz
    
    # 1. Kechagi ma'lumotni bazadan o'qish
    try:
        old_df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
    except sqlite3.OperationalError:
        # Jadval hali yaratilmagan bo'lsa (birinchi marta ishga tushganda)
        old_df = pd.DataFrame()
        
    # 2. Bugungi ma'lumotlarni SQLite'ga saqlash (Ertaga solishtirish uchun)
    current_df.to_sql(table_name, conn, if_exists='replace', index=False)
    
    # 3. Taqqoslash
    if old_df.empty:
        return "Bu fayl bo'yicha eski ma'lumot topilmadi. Bugungi holat xotiraga saqlandi."
    
    # Qatorlarni matn ko'rinishiga o'tkazib solishtirish (aniq farqlarni topish uchun)
    old_str = old_df.astype(str)
    new_str = current_df.astype(str)
    
    added = new_str[~new_str.apply(tuple,1).isin(old_str.apply(tuple,1))]
    removed = old_str[~old_str.apply(tuple,1).isin(new_str.apply(tuple,1))]
    
    return f"Yangi qo'shilgan yozuvlar: {len(added)} ta\nO'chirilgan yozuvlar: {len(removed)} ta"

async def send_daily_report():
    files = get_files_in_folder()
    
    if not files:
        await bot.send_message(chat_id=ADMIN_ID, text="⚠️ Papkada hech qanday fayl topilmadi.")
        return
        
    for file in files:
        try:
            current_data = get_sheet_data(file['id'])
            report_text = compare_and_save(file['name'], current_data)
            
            final_message = f"📊 <b>{file['name']}</b> bo'yicha hisobot:\n\n{report_text}"
            await bot.send_message(chat_id=ADMIN_ID, text=final_message, parse_mode="HTML")
            
        except Exception as e:
            await bot.send_message(chat_id=ADMIN_ID, text=f"❌ {file['name']} faylini o'qishda xatolik: {str(e)}")

async def main():
    scheduler = AsyncIOScheduler(timezone='Asia/Tashkent')
    scheduler.add_job(send_daily_report, trigger='cron', hour=21, minute=0)
    scheduler.start()
    
    print("Bot ishga tushdi va Drive papkasini nazorat qilmoqda...")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())