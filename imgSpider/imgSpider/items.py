# Define here the models for your scraped items
#
# See documentation in:
# https://docs.scrapy.org/en/latest/topics/items.html

import scrapy


class ImgspiderItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    pass

class ImgItem(scrapy.Item):
    img_name = scrapy.Field()
    img_link = scrapy.Field()
    img_project_name = scrapy.Field()
    img_project_link = scrapy.Field()
    img_project_cat = scrapy.Field()
    img_project_tags = scrapy.Field()
    img_project_id = scrapy.Field()
    img_project_dir = scrapy.Field()