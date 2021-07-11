from datetime import timezone, timedelta, datetime, date
from os import system, getenv

import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from icalendar.prop import vText, vUri
from icalendar.parser import Parameters

文件名 = 'rocket_calendar.ics'
默认时区 = timezone(timedelta(hours=8), name='Asia/Shanghai')
网址 = 'http://www.spaceflightfans.cn/global-space-flight-schedule/action~agenda/page_offset~%d/request_format~json?request_type=json&ai1ec_doing_ajax=true'

def 打开文件():
    with open(文件名, 'rb') as 文件:
        日历 = 文件.read()
        return Calendar.from_ical(日历)

def 写入文件(写入内容):
    with open(文件名, 'wb') as 文件:
        文件.write(写入内容)

def 自动提交():
    system('git config --global user.email "26922dd@sina.com"')
    system('git config --global user.name "周盛道"')
    system('git config --global core.autocrlf true')
    system('git add .')
    system('git commit -m \'%s 自动更新\'' % datetime.now(tz=默认时区).strftime('%Y-%m-%dT%H:%M:%S'))
    system('git push')

def 获取页码(日历):
    
    需抓取页码 = [-1, 0]

    当前时间 = datetime.now(tz=默认时区).date()
    第一页修改时间 = datetime.strptime(日历['x-1-edt'], "%Y-%m-%dT%H:%M:%S").date()
    第二页修改时间 = datetime.strptime(日历['x-2-edt'], "%Y-%m-%dT%H:%M:%S").date()
    其他页修改时间 = datetime.strptime(日历['x-o-edt'], "%Y-%m-%dT%H:%M:%S").date()

    if (当前时间 - 第一页修改时间).days >= 1:
        需抓取页码.append(1)
    if (当前时间 - 第二页修改时间).days >= 30:
        需抓取页码.append(2)
    if (当前时间 - 其他页修改时间).days >= 365:
        需抓取页码.append('~')
        需抓取页码.append('*')

    return 需抓取页码

def 抓取(url):
    '''发送请求'''

    请求头 = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.141 Safari/537.36 Edg/90.0.818.56', 
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 
        'Accept-Language': 'zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2',
        'Accept-Encoding': 'deflate',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Cache-Control': 'no-cache'
    }

    结果 = requests.get(url, headers=请求头)
    print(结果.status_code, 结果.url)

    结果 = 结果.json()
    return 结果['html']['dates']

def 处理结果(数据, 日历):
    for 日期 in 数据:
        事件集 = 数据[日期]['events']['allday'] + 数据[日期]['events']['notallday']
        # 倒序循环，避免下标错误
        for 下标 in range(len(事件集)-1, -1, -1):
            事件 = 事件集[下标]
            事件['date'] = 日期
            if 修改事件(事件, 日历):
                del 事件['date']
                事件集.remove(事件)
        if len(事件集) > 0:
            for 事件 in 事件集:
                事件['date'] = 日期
                新建事件(事件, 日历)

def 获取日期(事件):
    开始时间 = 结束时间 = 0
    参数 = {'tzid': 'Asia/Shanghai'}
    日期时间 = datetime.fromtimestamp(int(事件['date']), tz=默认时区)
    if 事件['is_allday'] == '1':
        开始时间 = 日期时间.date()
        结束时间 = 日期时间.date()
    elif 事件['is_multiday'] == '1':
        开始时间 = 日期时间.date()
        日期时间 = date(int(事件['enddate_info']['year']), 
                int(事件['enddate_info']['month'][:-1]), 
                int(事件['enddate_info']['day']))
        结束时间 = 日期时间
    else:
        日期时间 = datetime(日期时间.year, 日期时间.month, 日期时间.day, 
                int(事件['short_start_time'].split(':')[0]), 
                int(事件['short_start_time'].split(':')[1]), tzinfo=默认时区)
        开始时间 = 日期时间
        结束时间 = 日期时间
    return (开始时间, 结束时间, 参数)

def 事件属性写入(事件, 日历事件, 标志=False):
    日期时间 = 获取日期(事件)
    日历事件['class'] = vText('PUBLIC')
    日历事件['url'] = vUri(事件['permalink'])
    日历事件['location'] = vText(事件['venue'])
    日历事件['uid'] = vText(事件['post_id'])
    日历事件['summary'] = vText(事件['filtered_title'])
    日历事件['description'] = vText(事件['post_excerpt'])
    日历事件['categories'] = BeautifulSoup(事件['categories_html'], 
            'html.parser').get_text(',', strip=True).split(',')
    if 标志:
        日历事件.add('dtstart', 日期时间[0], 日期时间[2])
        日历事件.add('dtend', 日期时间[1], 日期时间[2])
    else:
        日历事件['dtstart'].dt = 日期时间[0]
        日历事件['dtstart'].params = Parameters(日期时间[2])
        日历事件['dtend'].dt = 日期时间[1]
        日历事件['dtend'].params = Parameters(日期时间[2])

def 新建事件(事件, 日历):
    日历事件 = Event()
    日历.add_component(日历事件)
    事件属性写入(事件, 日历事件, 标志=True)

def 修改事件(事件, 日历):
    for 日历事件 in 日历.subcomponents:
        if 日历事件['UID'] == 事件['post_id']:
            事件属性写入(事件, 日历事件)
            return True
    return False

def 主函数():
    日历 = 打开文件()
    需抓取页码 = 获取页码(日历)
    修改时间 = vText(datetime.now(tz=默认时区).strftime('%Y-%m-%dT%H:%M:%S'))
    for 页码 in 需抓取页码:
        退出 = 0
        if 页码 == '~':
            页码 = -2
            while 退出 < 2:
                结果 = 抓取(网址 % 页码)
                页码 -= 1
                if len(结果) == 0:
                    退出 += 1
                    continue
                处理结果(结果, 日历)
        elif 页码 == '*':
            页码 = 3
            while 退出 < 2:
                结果 = 抓取(网址 % 页码)
                页码 += 1
                if len(结果) == 0:
                    退出 += 1
                    continue
                处理结果(结果, 日历)
            日历['x-o-edt'] = 修改时间
        else:
            结果 = 抓取(网址 % 页码)
            处理结果(结果, 日历)
            if 页码 == 1:
                日历['x-1-edt'] = 修改时间
            elif 页码 == 2:
                日历['x-2-edt'] = 修改时间
    写入文件(日历.to_ical())
    if getenv('CI') == 'true':
        自动提交()

if __name__ == '__main__':
    主函数()
