from __future__ import unicode_literals

import os
import configparser
import json, ssl, urllib.request
# from tkinter import E
import copy
import random
# from select import select
# from pickle import TRUE
# import requests
import psycopg2
from flask import Flask, request, abort
from flask_sqlalchemy import SQLAlchemy
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import *

app = Flask(__name__)

# 讀取config.ini裡頭的 channel_access_token, channel_secret
config = configparser.ConfigParser()
config.read('config.ini')
line_bot_api = LineBotApi(config.get('line-bot', 'channel_access_token'))
handler = WebhookHandler(config.get('line-bot', 'channel_secret'))

# 接收 LINE 的資訊
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']

    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    
    try:
        handler.handle(body, signature)
        
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


# 與資料庫做連線
conn = psycopg2.connect(database="d6mkd8npubjjdd",
						user="zdimqbfmrotyif",
						password="258ed27adec8a77f93d0d790befc7c0b3ac9810d8a67b6d63aeb9f2360f1846a",
						host="ec2-44-207-253-50.compute-1.amazonaws.com",
						port="5432")
print("Opened database successfully")
cursor = conn.cursor()

# 線上json解析_流浪動物
url = 'https://data.coa.gov.tw/Service/OpenData/TransService.aspx?UnitId=QcbUEzN6E6DL'
context = ssl._create_unverified_context()
with urllib.request.urlopen(url, context=context) as jsondata:
    #將JSON進行UTF-8的BOM解碼，並把解碼後的資料載入JSON陣列中
    Animal_data = json.loads(jsondata.read().decode('utf-8-sig')) 

# 本地json解析_流浪動物
# Animal_data = json.load(open('json/TransService.json','r', encoding = 'utf-8'))


# 本地json解析_動物收容所
Shelter_data = json.load(open('json/animal_Shelter_data.json','r', encoding = 'utf-8'))

# 本地json解析_動物醫院
Hosp_data = json.load(open('json/animal_Hosp_data.json','r', encoding = 'utf-8'))

# 本地json解析_動物食品
Food_data = json.load(open('json/dog_Food_data.json','r', encoding = 'utf-8'))

# 要執行的動作
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    userid = event.source.user_id
    sql_cmd = "select * from userdata where uid='" + userid + "'"
    cursor.execute(sql_cmd)
    query_data = cursor.fetchall()
    if len(query_data) == 0:
        sql_cmd = "insert into userdata (uid, state, county) values('" + userid + "', 'no', 'no');"
        cursor.execute(sql_cmd)
        conn.commit()
    else:
        cursor.execute(sql_cmd)
        rows = cursor.fetchall()
        uid = rows[0][1]
        mode = rows[0][2]
        county = rows[0][3]

    user_text = event.message.text
    if user_text == '介紹':
        sendUse(event, userid)
    elif user_text == '動物醫院':
        sql_cmd = "update userdata set state='hosp', county='no' where uid='" + userid +"'"
        cursor.execute(sql_cmd)
        conn.commit()
        message = "進入查詢模式：動物醫院\n請輸入所在縣市"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )
    elif user_text == '動物收容所': 
        sql_cmd = "update userdata set state='shelter', county='no' where uid='" + userid +"'"
        cursor.execute(sql_cmd)
        conn.commit()
        message = "進入查詢模式：動物收容所\n請輸入所在縣市"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )
    elif user_text == '領養': 
        sql_cmd = "update userdata set state='adoption', county='no' where uid='" + userid +"'"
        cursor.execute(sql_cmd)
        conn.commit()
        message = "進入查詢模式：動物領養\n請輸入所在縣市"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )
    elif user_text == '重新選擇': 
        sql_cmd = "update userdata set state='no', county='no' where uid='" + userid +"'"
        cursor.execute(sql_cmd)
        conn.commit()
        message = "以清除紀錄，請重新點擊查詢選單"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )
    elif user_text == '寵物食品':
        dog_food(event)
    elif user_text == '狀態':
        mod = ""
        if mode == "hosp":
            mod = "醫院"
        elif mode == "shelter":
            mod = "收容所"
        else:
            mod = "無"
        message = "正在查詢：" + mod + "\n" + "鄉政市區：" + county

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=message)
        )
    else:
        selected(event, user_text, userid, mode, county)

# 使用說明
def sendUse(event, userid):
    try:
        FlexMessage = json.load(open('json/sendUse_Flex.json','r', encoding = 'utf-8'))
        flex_message = FlexSendMessage(alt_text = '使用說明', contents = FlexMessage)
        line_bot_api.reply_message(
            event.reply_token,
            flex_message
        )
    except:
        sql_cmd = "update userdata set state='no', digit3='no' where uid='" + userid +"'"
        cursor.execute(sql_cmd)
        conn.commit()
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text='使用說明：錯誤！'))

# 狀態選擇
def selected(event, user_text, userid, mode, county):
    if mode == 'hosp':
        if county != "no":
            print("鄉鎮市區")
            hosp_City(event, user_text, userid, county)
        else:     
            hosp_County(event, user_text, userid)
    elif mode == 'shelter':
        shelter(event, user_text, userid)
    elif mode == 'adoption':
        adoption(event, user_text, userid)
    else:
        chat(event, user_text)

# 醫院資訊輸出_S
def hosp_County(event, user_text, userid):
    try:
        if user_text[0] == "台":
            user_text_new = user_text.replace("台", "臺")
        else:
            user_text_new = user_text

        # 原始json格式
        FlexMessage = json.load(open('json/Hosp_Flex.json','r', encoding = 'utf-8'))
        # 用於修改圖文資料
        FlexMessageNew = copy.copy(FlexMessage['contents'][0])
        # 清除
        FlexMessage['contents'].clear()
        City = ""
        for i in range(len(Hosp_data)):
            if user_text_new in Hosp_data[i]["City"]:
                City = Hosp_data[i]["City"]
                FlexMessageNew['body']['contents'][0]['text'] = Hosp_data[i]["Name"]  #醫院名稱
                FlexMessageNew['body']['contents'][1]['text'] = Hosp_data[i]["Address"]      #醫院地址
                
                phonenum = ""
                if Hosp_data[i]["Tel"] == "":
                    phonenum = "無"
                else:
                    phonenum = Hosp_data[i]["Tel"]
                FlexMessageNew['body']['contents'][2]['contents'][0]['contents'][1]['text'] = phonenum  #電話

                IsED = ""
                if Hosp_data[i]["IsEmergencyDepartment"]:
                    IsED = "提供急診"
                else:
                    IsED = "不提供急診"
                FlexMessageNew['body']['contents'][2]['contents'][1]['contents'][1]['text'] = IsED   #說明
                
                FlexMessage['contents'].append(copy.deepcopy(FlexMessageNew))
        if len(FlexMessage['contents']) == 0:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='醫院資訊：請重新輸入所在縣市！'))
        if len(FlexMessage['contents']) > 10:
            sql_cmd = "update userdata set county='" + City + "' where uid='" + userid + "'"
            cursor.execute(sql_cmd)
            conn.commit()
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text='由於數量過多，請輸入所在鄉鎮市區！'))
        else:
            flex_message = FlexSendMessage(alt_text = 'hello', contents = FlexMessage)
            line_bot_api.reply_message(event.reply_token, flex_message)
            # line_bot_api.reply_message(event.reply_token,TextSendMessage(text='輸出！'))
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='醫院資訊：錯誤！'))

# 醫院資訊輸出_鄉鎮市區
def hosp_City(event, user_text, userid, county):
    try:
        if user_text[0] == "台":
            user_text_new = user_text.replace("台", "臺")
        else:
            user_text_new = user_text
        # 原始json格式
        FlexMessage = json.load(open('json/Hosp_Flex.json','r', encoding = 'utf-8'))
        # 用於修改圖文資料
        FlexMessageNew = copy.copy(FlexMessage['contents'][0])
        # 清除
        FlexMessage['contents'].clear()

        hosp_City_arr = []
        for i in range(len(Hosp_data)):
            if county == Hosp_data[i]["City"] and user_text_new in Hosp_data[i]["Address"]:
                FlexMessageNew['body']['contents'][0]['text'] = Hosp_data[i]["Name"]  #醫院名稱
                FlexMessageNew['body']['contents'][1]['text'] = Hosp_data[i]["Address"]      #醫院地址
                
                phonenum = ""
                if Hosp_data[i]["Tel"] == "":
                    phonenum = "無"
                else:
                    phonenum = Hosp_data[i]["Tel"]
                FlexMessageNew['body']['contents'][2]['contents'][0]['contents'][1]['text'] = phonenum  #電話

                IsED = ""
                if Hosp_data[i]["IsEmergencyDepartment"]:
                    IsED = "提供急診"
                else:
                    IsED = "不提供急診"
                FlexMessageNew['body']['contents'][2]['contents'][1]['contents'][1]['text'] = IsED   #說明

                hosp_City_arr.append(copy.deepcopy(FlexMessageNew))

        if len(hosp_City_arr) == 0:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='醫院資訊：請重新輸入所在鄉鎮市區！'))

        # 隨機抽樣 10筆
        for n in [random.randint(0, len(hosp_City_arr)) for _ in range(10)]:
            print(hosp_City_arr[n]['body']['contents'][0]['text'])
            FlexMessage['contents'].append(copy.deepcopy(hosp_City_arr[n]))
        
        try:
            flex_message = FlexSendMessage(alt_text = 'hello', contents = FlexMessage)
            line_bot_api.reply_message(event.reply_token, flex_message)
        except:
            line_bot_api.reply_message(event.reply_token,TextSendMessage(text='醫院鄉鎮市區資訊1：錯誤！'))
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='醫院鄉鎮市區資訊：錯誤！'))

# 收容所資訊輸出
def shelter(event, user_text, userid):
    try:
        if user_text[0] == "台":
            user_text_new = user_text.replace("台", "臺")
        else:
            user_text_new = user_text
        
        # 原始json格式
        FlexMessage = json.load(open('json/Shelter_Flex.json','r', encoding = 'utf-8'))
        # 用於修改圖文資料
        FlexMessageNew = FlexMessage['contents'][0]
        # 清除
        FlexMessage['contents'].clear()

        for i in range(len(Shelter_data)):
            if user_text_new in Shelter_data[i]["CountyName"]:
                #FlexMessageNew['hero']['url'] = "www"
                FlexMessageNew['body']['contents'][0]['text'] = Shelter_data[i]["ShelterName"]  #收容所名稱
                FlexMessageNew['body']['contents'][1]['text'] = Shelter_data[i]["Address"]      #收容所地址
                FlexMessageNew['body']['contents'][2]['contents'][0]['contents'][1]['text'] = Shelter_data[i]["Tel"]    #電話
                FlexMessageNew['body']['contents'][2]['contents'][1]['contents'][1]['text'] = Shelter_data[i]["Memo"]   #說明
                WebLink = ""
                if Hosp_data[i]["WebSite"] == "":
                    WebLink = "https://i.imgur.com/mtPs8fl.png"
                else:
                    WebLink = Shelter_data[i]["link"]
                FlexMessageNew['footer']['contents'][0]['action']['uri'] = WebLink  #網站鏈結
                FlexMessage['contents'].append(copy.deepcopy(FlexMessageNew))
        
        if len(FlexMessage['contents']) == 0:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text='收容所資訊：請重新輸入所在縣市！'))
        else:
            flex_message = FlexSendMessage(alt_text = 'hello', contents = FlexMessage)
            line_bot_api.reply_message(event.reply_token, flex_message)
        
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='收容所資訊：錯誤！'))

# 領養
def adoption(event, user_text, userid):
    try:
        if user_text[0] == "台":
            user_text_new = user_text.replace("台", "臺")
        else:
            user_text_new = user_text
        
        # 原始json格式
        FlexMessage = json.load(open('json/animal_Flex.json','r', encoding = 'utf-8'))
        animal_arr = []
        for i in range(len(Animal_data)):
            if user_text_new in Animal_data[i]['shelter_address']:
                FlexMessage['body']['contents'][0]['text'] = Animal_data[i]['animal_Variety']   # 品種
                FlexMessage['body']['contents'][1]['contents'][0]['contents'][1]['text'] = Animal_data[i]['animal_kind']        # 類別
                FlexMessage['body']['contents'][1]['contents'][1]['contents'][1]['text'] = Animal_data[i]['animal_sex']         # 性別
                FlexMessage['body']['contents'][1]['contents'][2]['contents'][1]['text'] = Animal_data[i]['animal_foundplace']  # 來源
                FlexMessage['body']['contents'][1]['contents'][3]['contents'][1]['text'] = Animal_data[i]['animal_place']       # 我在
                FlexMessage['body']['contents'][1]['contents'][4]['contents'][1]['text'] = Animal_data[i]['animal_colour']      # 毛色
                FlexMessage['body']['contents'][1]['contents'][5]['contents'][1]['text'] = Animal_data[i]['shelter_tel']        # 領養電話
                FlexMessage['body']['contents'][1]['contents'][6]['contents'][1]['text'] = Animal_data[i]['album_file']         # 圖片來源
                animal_arr.append(copy.deepcopy(FlexMessage))

        rdnum = random.randint(0, len(animal_arr))
        # print(len(animal_arr))
        # print(animal_arr[rdnum]['body']['contents'][1]['contents'][2]['contents'][1]['text'])
        FlexMessage['body'] = animal_arr[rdnum]['body']
        FlexMessage['hero']['url'] = FlexMessage['body']['contents'][1]['contents'][6]['contents'][1]['text']
        try:
            if len(FlexMessage['body']['contents']) == 0:
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text='領養資訊：請重新輸入所在縣市！'))
            else:
                flex_message = FlexSendMessage(alt_text = 'hello', contents = FlexMessage)
                line_bot_api.reply_message(event.reply_token, flex_message)
        except:
            if FlexMessage['hero']['url'] == "":
                FlexMessage['hero']['url'] = "https://i.imgur.com/mtPs8fl.png"
            flex_message = FlexSendMessage(alt_text = 'hello', contents = FlexMessage)
            line_bot_api.reply_message(event.reply_token, flex_message)
        
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='領養資訊：錯誤！'))

def dog_food(event):
    try:
        # 原始json格式
        FlexMessage = json.load(open('json/Food_Flex.json','r', encoding = 'utf-8'))

        rdnum = random.randint(0, len(Food_data))
        FlexMessage['body']['contents'][0]['text'] = Food_data[rdnum]['name']
        FlexMessage['body']['contents'][1]['text'] = Food_data[rdnum]['introduce']
        flex_message = FlexSendMessage(alt_text = 'hello', contents = FlexMessage)
        line_bot_api.reply_message(event.reply_token, flex_message)
    except:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text='領養資訊：錯誤！'))

# 聊天
def chat(event, user_text):
    line_bot_api.reply_message(event.reply_token,TextSendMessage(text=event.message.text))

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5100))
    app.run(host='0.0.0.0', port = port)