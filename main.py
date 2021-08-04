from datetime import timezone, timedelta, datetime, date
from os import getenv, system, environ
from logging import basicConfig, INFO, info, error

import requests
from bs4 import BeautifulSoup
from icalendar import Calendar, Event
from icalendar.prop import vText, vUri
from icalendar.parser import Parameters

文件名 = 'rocket_calendar.ics'
默认时区 = timezone(timedelta(hours=8), name='Asia/Shanghai')
当前时间 = datetime.now(tz=默认时区)
提交消息 = '%s 自动更新' % 当前时间.strftime('%Y-%m-%dT%H:%M:%S%z')
推送网址 = 'http://pushplus.hxtrip.com/send'
网址 = 'http://www.spaceflightfans.cn/global-space-flight-schedule/action~agenda/page_offset~%d/request_format~json?request_type=json&ai1ec_doing_ajax=true'

basicConfig(level=INFO, filename="test.log", filemode="w", encoding='utf-8',
            format="%(asctime)s L%(lineno)s %(funcName)s() => %(levelname)s:%(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z")


def 打开文件():
    with open(文件名, 'rb') as 文件:
        日历 = 文件.read()
        return Calendar.from_ical(日历)


def 自动提交(内容):
    with open(文件名, 'wb') as 文件:
        文件.write(内容)
    结果 = requests.put('http://icalx.com/public/zhoushengdao/rocket_calendar.ics',
                      auth=('zhoushengdao', environ['ICALX_PASSWORD']), data=内容)
    info("%s %s" % (结果.status_code, 结果.url))
    if getenv('CI') == 'true':
        system('git config --global user.email "26922dd@sina.com"')
        system('git config --global user.name "周盛道"')
        system('git config --global core.autocrlf true')
        system('git add .')
        system('git commit -m \'%s\'' % 提交消息)
        system('git push')


def 获取页码(日历):

    需抓取页码 = [-1, 0]

    当前日期 = 当前时间.date()
    第一页修改时间 = datetime.strptime(日历['x-1-edt'], "%Y-%m-%dT%H:%M:%S").date()
    第二页修改时间 = datetime.strptime(日历['x-2-edt'], "%Y-%m-%dT%H:%M:%S").date()
    其他页修改时间 = datetime.strptime(日历['x-o-edt'], "%Y-%m-%dT%H:%M:%S").date()

    if (当前日期 - 第一页修改时间).days >= 1:
        需抓取页码.append(1)
    if (当前日期 - 第二页修改时间).days >= 30:
        需抓取页码.append(2)
    if (当前日期 - 其他页修改时间).days >= 365:
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
    info("%s %s" % (结果.status_code, 结果.url))

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
    return (开始时间, 结束时间)


def 事件属性写入(事件, 日历事件, 新建=False):
    日期时间 = 获取日期(事件)
    参数 = {'tzid': 'Asia/Shanghai'}
    日历事件['class'] = vText('PUBLIC')
    日历事件['url'] = vUri(事件['permalink'])
    日历事件['location'] = vText(事件['venue'])
    日历事件['uid'] = vText(事件['post_id'])
    日历事件['summary'] = vText(事件['filtered_title'])
    日历事件['description'] = vText(BeautifulSoup(事件['post_excerpt'],
                                              'html.parser').get_text())
    标签 = BeautifulSoup(事件['categories_html'],
                       'html.parser').get_text(',', strip=True)
    标签 += ','
    标签 += BeautifulSoup(事件['tags_html'],
                        'html.parser').get_text(',', strip=True)
    日历事件['categories'] = 标签.split(',')
    if 新建:
        日历事件.add('dtstart', 日期时间[0], 参数)
        日历事件.add('dtend', 日期时间[1], 参数)
    else:
        日历事件['dtstart'].dt = 日期时间[0]
        日历事件['dtstart'].params = Parameters(参数)
        日历事件['dtend'].dt = 日期时间[1]
        日历事件['dtend'].params = Parameters(参数)


def 新建事件(事件, 日历):
    日历事件 = Event()
    日历.add_component(日历事件)
    事件属性写入(事件, 日历事件, 新建=True)


def 修改事件(事件, 日历):
    for 日历事件 in 日历.subcomponents:
        if 日历事件['UID'] == 事件['post_id']:
            事件属性写入(事件, 日历事件)
            return True
    return False


def 主函数():
    日历 = 打开文件()
    需抓取页码 = 获取页码(日历)
    修改时间 = vText(当前时间.strftime('%Y-%m-%dT%H:%M:%S'))
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
    自动提交(日历.to_ical())


if __name__ == '__main__':
    try:
        主函数()
    except Exception as 错误:
        提交消息 += ' 错误'
        error(错误)

    environ['PUSH_TOKEN'] = 'f4d6ff7b044a46b08524b216f9e9e186'
    with open("test.log", "rt", encoding="utf-8") as 日志:
        内容 = 日志.read()
        print(内容)
        结果 = requests.post(推送网址, json={
                           'token': environ['PUSH_TOKEN'],
                           'title': 提交消息,
                           'content': 内容.replace('\n', '<br>'),
                           'template': 'html'})
        print("%s L%s %s() => %s:%s %s" % (datetime.now(tz=默认时区).strftime('%Y-%m-%dT%H:%M:%S%z'), 211, '<module>', 'INFO', 结果.status_code, 结果.url))
