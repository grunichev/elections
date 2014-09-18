# -*- coding: utf-8 -*-
import urllib2
from bs4 import BeautifulSoup
import mysql.connector as MySQLdb
import os

DATABASE = {
    'user': "root",
    'password': '',
    'database': "elections",
    'host': '',
}

def get_db_connection():
    db = MySQLdb.connect(**DATABASE)
    c = db.cursor()
    return c, db

def get_soup(url):
    print url
    page = urllib2.urlopen(url).read()
    page = page.decode('cp1251').encode('utf8')
    soup = BeautifulSoup(page)
    return soup, page

def prepare_tables():
    q = "drop table if exists elections;"
    con.execute(q)
    db.commit()
    q = "drop table if exists districts;"
    con.execute(q)
    db.commit()
    q = "drop table if exists district_rows;"
    con.execute(q)
    db.commit()
    q = """create table elections (id int primary key auto_increment,
        name varchar(200), href varchar(255));"""
    con.execute(q)
    db.commit()
    q = """create table districts (id int primary key auto_increment,
        election_id int,
        parent_id int, name varchar(200), href varchar(255) null);"""
    con.execute(q)
    db.commit()
    q = """create table district_rows(id int primary key auto_increment,
        district_id int, row_num int, value int);"""
    con.execute(q)
    db.commit()

def save_election(name, href):
    q = "insert into elections (name, href) values (%s, %s)"
    con.execute(q, (name, href))
    db.commit()
    return con.lastrowid

def save_district(election_id, name, href, parent_id=None):
    q = """insert into districts (election_id, name, href, parent_id)
    values (%s, %s, %s, %s)"""
    con.execute(q, (election_id, name, href, parent_id))
    db.commit()
    return con.lastrowid

def save_row(district_id, row_num, value):
    q = """insert into district_rows (district_id, row_num, value)
    values (%s, %s, %s)"""
    con.execute(q, (district_id, row_num, value))
    db.commit()
    return con.lastrowid

def save_page(election_id, title, page):
    mo = ''
    if election_id > 1:
        mo = 'mo/'
    name = "downloads/%s%s.html" % (mo, title)
    with open(name, "w") as f:
        f.write(page)

def parse_table(election_id, soup, parent_id=None, href=None, page=None):
    data_table = soup.findAll('table', {'style': 'width:100%;border-color:#000000'})
    tables = data_table[0].findAll('table')
    table = tables[1]

    rows = table.findAll('tr')
    row_num = 0
    was_empty_line = False
    districts = []
    for row in rows:
        tds = row.findAll('td')
        raised = False
        for td_id, td in enumerate(tds):
            if row_num == 0:
                a = td.nobr.a
                if a:
                    text = a.text
                    href = a['href']
                else:
                    text = td.nobr.text

                d_id = save_district(election_id, text, href, parent_id)
                save_page(election_id, text, page)
                districts.append({'id': d_id, 'href': href})
            else:
                district_id = districts[td_id]['id']
                try:
                    value = int(td.nobr.b.text)
                except:
                    assert not was_empty_line
                    assert row_num == 14
                    was_empty_line = True
                    raised = True
                    break
                save_row(district_id, row_num, value)
        if raised:
            continue
        row_num += 1
    return districts

for directory in ('downloads', 'downloads/mo'):
    if not os.path.exists(directory):
        os.makedirs(directory)

con, db = get_db_connection()
prepare_tables()

url = 'http://www.st-petersburg.vybory.izbirkom.ru/region/st-petersburg/'
soup, page = get_soup(url)

res = soup.find('td', {'class': 'resultsCount'})
text = res.text
assert text.startswith(u'Всего найдено записей:')

blabla, num = text.split(':')
num = int(num)
links = soup.findAll('a', {'class': 'vibLink'})
assert len(links) == num

for link in links:
    election_id = save_election(link.text, link['href'])

    soup, page = get_soup(link['href'])
    links = soup.findAll('a')
    l = links[len(links)-1]
    mode = None
    print l.text
    if l.text == u'Сводная таблица предварительных итогов голосования' or \
            l.text == u'Сводная таблица результатов выборов':
        mode = 1
    if l.text == u'Сводная таблица предварительных итогов голосования по одномандатному (многомандатному) округу':
        mode = 2
    if not mode:
        raise

    soup, page = get_soup(l['href'])
    if mode == 2:
        options = soup.findAll('option')
        for option in options:
            try:
                option['value']
            except:
                continue
            print '-->' ,option['value']
            soup, page = get_soup(option['value'])
            parse_table(election_id, soup, href=option['value'], page=page)
    else:
        subdistricts = parse_table(election_id, soup, page=page)
        for sub in subdistricts:
            print sub['href']
            soup, page = get_soup(sub['href'])
            parse_table(election_id, soup, sub['id'], href=sub['href'], page=page)
