import scrapy
from scrapy import Request
from scrapy.shell import inspect_response
from scrapy.item import Item, Field

import json, os, time, requests
from hashlib import md5
from bs4 import BeautifulSoup
import chompjs

root_link = "https://ikon.mn"
    
class IkonSpider(scrapy.Spider):
    name='ikonspider'
    robotstxt_obey = True
    download_delay = 0.5
    user_agent = 'bayartsogt-crawler-for-nlp (bayartsogt.yadamsuren@gmail.com)'
    autothrottle_enabled = True
    httpcache_enabled = True

    def start_requests(self):
        start_urls = [
            (root_link+'/l/1' , "politics"  ), # улс төр
            (root_link+'/l/2' , "economy"   ), # эдийн засаг
            (root_link+'/l/3' , "society"   ), # нийгэм
            (root_link+'/l/16', "health"    ), # эрүүл мэнд
            (root_link+'/l/4' , "world"     ), # дэлхийд
            (root_link+'/l/7' , "technology"), # технологи
        ]
        for index, url_tuple in enumerate(start_urls):
            url      = url_tuple[0]
            category = url_tuple[1]
            yield Request(url, meta={'category': category}, dont_filter=True)

    def parse(self, response):
        news_title = response.xpath("//*[contains(@class, 'inews')]//h1/text()").extract()
        if (len(news_title)==0):
            print(">>>>>>>>>>>>> I'M GROOOOOOT ")
        else:
            news_title  = news_title[0].strip()
            news_body   = response.xpath("//*[contains(@class, 'icontent')]/descendant::*/text()[normalize-space() and not(ancestor::a | ancestor::script | ancestor::style)]").extract()
            news_date   = response.css('div[class*=time]::attr(rawdate)').get()
            news_author = response.xpath('//div[@class="name"]//text()')[-1].get().strip()
            news_body   = " ".join(news_body)
            url         = response.request.url
            category    = response.meta.get('category', 'default')
            hashed_name = md5(news_title.encode("utf-8")).hexdigest()

            reaction_relative_path = response.xpath("//*[contains(@id, 'ikon_reaction_container')]//@path").get()
            news_id = reaction_relative_path.split("/")[-1]

            # reaction retrieval
            soup = request_soup(f"{root_link}/reaction/{news_id}")
            values = [div.text.strip() for div in soup.findAll("div",{"class":"value"})]
            values = [int(v) if v!="" else 0 for v in values]
            keys = [div.attrs['rtext'].strip() for div in soup.findAll("div",{"class":"vote"})]
            reaction = dict(zip(keys,values))

            # comments retrieval
            soup = request_soup(f'{root_link}/c/{news_id}?tp=news&cp={int(time.time() * 1000)}')
            comments_js = ""
            for script in soup.find_all("script"): #,{"class":"value"}
                child = next(script.children)
                if "comments =" in child:
                    comments_js = str(child)
                    break
            
            comment = chompjs.parse_js_object(comments_js) if comments_js != "" else []

            data = {}
            data['title']       = news_title
            data['body' ]       = news_body
            data['date' ]       = news_date
            data['author']      = news_author
            data['url'  ]       = url
            data['news_id']     = news_id
            data['reaction']    = reaction
            data['comment']     = comment

            file_name = "./corpuses/"+category+"/"+hashed_name+".txt"
            os.makedirs(os.path.dirname(file_name), exist_ok=True)
            print("saving to ", file_name)
            with open(file_name, "w", encoding="utf8") as outfile:
                json.dump(data, outfile, ensure_ascii=False)

            #import pdb; pdb.set_trace()

        for next_page in response.xpath("//*[contains(@class, 'nlitem')]//a"):
            yield response.follow(next_page, self.parse, meta={'category': response.meta.get('category', 'default')})

        for next_page in response.xpath("//*[contains(@class, 'ikon-right-dir')]/parent::a"):
            yield response.follow(next_page, self.parse, meta={'category': response.meta.get('category', 'default')})

def request_soup(link: str) -> BeautifulSoup:
    """
    Create send request & return parset tree from BS4
    """
    res = requests.get(link)
    # print("Status code:", res.status_code)
    return BeautifulSoup(res.text, 'html.parser')