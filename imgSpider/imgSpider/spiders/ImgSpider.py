import asyncio
import logging
import os
import asyncio
import os
import pathlib
from io import BytesIO
import re
import aiofiles
import brotli
import scrapy
from PIL import Image
import win32com.client

class AsyncIdListManager:
    def __init__(self, file_path):
        self.file_path = file_path
        self.id_set = set()
        asyncio.get_event_loop().run_until_complete(self.load_ids())

    async def load_ids(self):
        if not os.path.exists(self.file_path):
            await self.save_to_file()
        async with aiofiles.open(self.file_path, 'r') as file:
            ids_str = await file.read()
            if ids_str:
                self.id_set = set(ids_str.split(','))

    def add_id(self, new_id):
        if new_id not in self.id_set:
            self.id_set.add(new_id)
            return asyncio.create_task(self._save_to_file())

    def check_duplicate(self, new_id):
        return new_id in self.id_set

    def save_to_file(self):
        return asyncio.create_task(self._save_to_file())

    async def _save_to_file(self):
        async with aiofiles.open(self.file_path, 'w') as file:
            await file.write(','.join(self.id_set))

    def is_empty(self):
        return not bool(self.id_set)

class imgSpider(scrapy.Spider):
    name = "imgSpider"
    allowed_domains = ['www.hentaiclub.net', 'cdn.sshs.rip']
    raw_dir = 'H:\\download\\hentaiclub'
    tagDir = 'H:\\download\\hentaiclub\\tags'
    file_path = "H:\\download\\hentaiclub\\ids.txt"
    manager = AsyncIdListManager(file_path)
    cookies = []

    def is_brotli_encoded(self, data):
        return data[:3] == b'\x1f\x8b\x08'

    def start_requests(self):
        urls = [
            "https://www.hentaiclub.net/sort/r18.html",
            "https://www.hentaiclub.net/sort/r15.html"
        ]
        self.mkDir(self.raw_dir)
        self.mkDir(self.tagDir)
        self.cookies = self.settings.getdict('COOKIES')

        for url in urls:
            dir_name = url.split("/")[-1].strip('.html')
            file_path = os.path.join(self.raw_dir, dir_name)
            print(file_path)
            self.mkDir(file_path)

            yield scrapy.Request(url=url, cookies=self.cookies , callback=self.parse)

        self.manager.save_to_file()

    def parse(self, response):
        if self.is_brotli_encoded(response.body):
            decompressed_content = brotli.decompress(response.body)
            response = response.replace(body=decompressed_content, encoding='utf-8')

        current_url = response.css('li.current a::attr(href)').get()
        next_url = response.css('li.next a::attr(href)').get()
        ims_project_urls = response.css('a.item-link::attr(href)').getall()

        if next_url:
            yield scrapy.Request(url=next_url, callback=self.parse, cookies=self.cookies, priority=1)

        for url in ims_project_urls:
            if not self.manager.check_duplicate(url.split("/")[-1].strip('.html')):
                yield scrapy.Request(url=url, callback=self.img_parse, cookies=self.cookies, priority=2)

    def img_parse(self, response):
        img = {
            'img_item_list': response.css('div.post-item'),
            'img_project_name': response.css('span.post-info-text::text').get(),
            'img_project_link': response.url,
            'img_project_tags': response.css('div.post-tags a::text').getall(),
            'img_project_id': response.url.split("/")[-1].strip('.html')
        }

        if not self.manager.check_duplicate(img['img_project_id']):
            parentDir = response.url.split("/")[-2]
            img['parent_path'] = os.path.join(self.raw_dir, parentDir, img['img_project_id'])
            self.mkDir(img['parent_path'])

            for tag_name in img['img_project_tags']:
                tag_path = os.path.join(self.tagDir, tag_name)
                self.mkDir(tag_path)
                # self.create_folder_shortcut(img['parent_path'], tag_path,
                #                                   img['img_project_name'] + str(img['img_project_id']) + ".lnk")
                try:
                    self.create_folder_shortcut(img['parent_path'], tag_path,
                                                img['img_project_name'] + str(img['img_project_id']) + ".lnk")
                except Exception as e:
                    print("\n" + "=" * 50 + " Exception Occurred " + "=" * 50)
                    print("Exception:", e)
                    print("img_project_name:", img['img_project_name'])
                    print("img_project_id:", img['img_project_id'])
                    print("name=" + img['img_project_name'] + str(img['img_project_id']) + ".lnk")
                    print("=" * 115 + "\n")

                    self.log_exception(e, img)

            for item in img['img_item_list']:
                img_url = item.css('div.post-item::attr(data-src)').get()
                title, img_index = item.css('div.post-item')[0].css('div.post-item::attr(data-caption)').re(
                    r'([^\[]*?)\[(.*?)\]')
                if len(img['img_project_name']) == 0 and len(title) > 0:
                    img['img_project_name'] = title.strip()

                img['img_name'] = img_index + ".png"
                img['img_raw_url'] = img_url

                yield scrapy.Request(url=img_url, callback=self.saveImg_parse, meta={'img': {
                    'img_name' : img['img_name'],
                    'parent_path': img['parent_path']
                }}, cookies=self.cookies, priority=3)

            self.manager.add_id(img['img_project_id'])

    def mkDir(self, path):
        pathlib.Path(path).mkdir(parents=True, exist_ok=True)

    def saveImg_parse(self, response):
        img = response.meta['img']
        image_data = response.body
        image = Image.open(BytesIO(image_data))

        save_path = os.path.join(img['parent_path'], img['img_name'])
        image.save(save_path, 'PNG')

        # 打印保存信息
        print(f"=== Saved image '{img['img_name']}' to '{img['parent_path']}' in PNG format.")

    def create_folder_shortcut_sync(self, folder_path, shortcut_path):
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.TargetPath = folder_path
        shortcut.Save()

    def create_folder_shortcut(self, raw_path, shortcut_path, shortcut_name):
        path = os.path.join(os.environ["USERPROFILE"], shortcut_path, self.sanitize_filename(shortcut_name))

        self.create_folder_shortcut_sync(raw_path, path)

    def sanitize_filename(self, filename):
        # 使用正则表达式过滤出文件名中的合法字符
        filename = re.sub(r'[^\w\s.-]', '', filename)
        # 将连续的空格替换成单个下划线
        filename = re.sub(r'\s+', '_', filename)
        # 返回添加了.lnk后缀的文件名
        filename = filename.replace('？', '')
        filename = filename.replace('?', '')

        # 只保留常见的英文字符
        filename = re.sub(r'[^a-zA-Z0-9_\s.-]', '', filename)

        return filename


    def add_id_to_file(self, id):
        file_path = r"H:\download\hentaiclub\ids_left.txt"

        try:
            with open(file_path, 'r') as file:
                ids = file.read().split(',')
                ids = [int(i) for i in ids if i.strip()]
        except FileNotFoundError:
            ids = []

        ids.append(id)

        with open(file_path, 'w') as file:
            file.write(','.join(map(str, ids)))



    def read_ids_from_file(self):
        ids_path = r"H:\download\hentaiclub\ids_left.txt"
        try:
            with open(ids_path, 'r') as file:
                ids = file.read().split(',')
                ids = [int(i) for i in ids if i.strip()]
        except FileNotFoundError:
            ids = []
        return ids

    def write_ids_to_file(self, ids):
        ids_path = r"H:\download\hentaiclub\ids_left.txt"
        with open(ids_path, 'w') as file:
            file.write(','.join(map(str, ids)))

    def log_exception(self, e, img):
        log_path = r"H:\download\hentaiclub\log.txt"
        ids = self.read_ids_from_file()
        with open(log_path, 'a') as log_file:
            log_file.write("\n" + "=" * 50 + " Exception Occurred " + "=" * 50 + "\n")
            log_file.write("Exception: {}\n".format(e))
            log_file.write("img_project_name: {}\n".format(img['img_project_name']))
            log_file.write("img_project_id: {}\n".format(img['img_project_id']))
            log_file.write("=" * 115 + "\n")
        ids.append(img['img_project_id'])
        self.write_ids_to_file(ids)

