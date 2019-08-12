# -*- coding: utf-8 -*-
"""Main module."""
import re
import shutil
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.structures import CaseInsensitiveDict


class _Logger:
    def send_info(self, message):
        print('INFO: ' + message)

    def send_warning(self, message):
        print('WARNING: ' + message)

    def send_error(self, message):
        print('ERROR: ' + message)


class OtzovikCom:
    BASE_URL = 'https://otzovik.com/'
    REVIEWS_URL = urljoin(BASE_URL, 'reviews/')
    DEBUG = False
    title = None
    show_count = None
    count = None

    def __init__(self, slug, logger=_Logger()):
        self.reviews_url = urljoin(self.REVIEWS_URL, slug)
        self.reviews = list()
        self.logger = logger
        self.rating = Rating()
        self.slug = slug
        self.session = requests.Session()
        headers = CaseInsensitiveDict({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel'
                          ' Mac OS X x.y; rv:10.0)'
                          ' Gecko/20100101 Firefox/10.0',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Host': 'keep-alive',
            'Connection': 'otzovik.com',
            'Accept-Language': 'ru-MD,en-US;q=0.7,en;q=0.3',
            'DNT': '1',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
            'TE': 'Trailers',
        })
        self.session.headers = headers

    def start(self, exclude_ids=None):
        if exclude_ids is None:
            exclude_ids = list()
        page = 1
        page_one_soup = self._get_page(page)
        self._get_info_company(page_one_soup)

        all_reviews_ids = list(self._get_ids_of_reviews(page_one_soup))

        page += 1
        while not len(all_reviews_ids) == self.count:
            page_soup = self._get_page(page)

            if not page_soup.find_all('div', class_='item', itemprop='review'):
                break
            all_reviews_ids.extend(self._get_ids_of_reviews(page_soup))
            page += 1
        actual_reviews_ids = list(set(all_reviews_ids) - set(exclude_ids))
        for review_id in actual_reviews_ids:
            self.collect_review(review_id)
        return self

    def collect_review(self, review_id):
        url = urljoin(self.BASE_URL, 'review_{}.html'.format(review_id))
        resp = resp = self.request('GET', url)
        if not resp.status_code == 200:
            self.logger.send_error(resp.text)
            raise Exception(resp.text)
        soup = BeautifulSoup(resp.text, 'html.parser')
        new_review = Review()
        new_review.title = soup.find('h1').text
        new_review.date = soup.select_one(
            'div.postdate-line>span.review-postdate.dtreviewed>abbr').attrs[
            'title']
        soup.select_one('div.review-bar>span>b').decompose()
        new_review.like = int(soup.select_one('div.review-bar>span').text)
        new_review.id = self._convert_string_to_int(
                                soup.select_one('div.review-bar>a')['href'])
        new_review.disadvantages = soup.select_one('div.review-plus').text
        new_review.disadvantages = soup.select_one('div.review-minus').text
        new_review.text = soup.select_one('div.review-body.description').text
        new_review.rating.average_rating = self._convert_string_to_int(
            soup.select_one('div.product-rating.tooltip-right').attrs['title'])
        author = Author()
        author_soup = soup.select_one('div.review-contents>'
                                      'div[itemprop="author"]')
        author.name = soup.select_one('div.login-col>a.user-login>span').text
        if author_soup.select_one('div.karma.karma1'):
            author.reputation = \
                int(author_soup.select_one('div.karma.karma1').text)
        author.count_reviews = int(
            author_soup.select_one('div.reviews-col>div>a').text)
        author.time_of_use = self._get_attribute('Время использования')
        author.cost = self._get_attribute('Стоимость')
        author.year_visit = self._get_attribute('Год посещения')
        author.country = self._get_attribute('Страна')
        author.township = self._get_attribute('Регион (край, область, штат)')
        author.district = self._get_attribute('Район')
        author.street = self._get_attribute('Улица')
        author.house = self._get_attribute('Дом №')
        new_review.overall_impression = self._get_attribute('Общее впечатление')

        new_review.ratings = self._get_review_ratings()
        new_review.author = author
        is_recommend_friends = self._get_attribute('Рекомендую друзьям')
        if is_recommend_friends == 'ДА':
            new_review.is_recommend_friends = True
        else:
            new_review.is_recommend_friends = False
        self.reviews.append(new_review)

    def _get_review_ratings(self):
        ratings = {}
        ratings_soup = self.soup.select('div.review-contents'
                                         '>div.product-rating-details>div')
        for rating_soup in ratings_soup:
            title = str(rating_soup.text).rstrip().replace('\n', '')
            rating = self._convert_string_to_int(rating_soup.contents[3].next.attrs['style'])
            ratings[title] = rating / 20
        return ratings

    def _get_attribute(self, title):
        table_soup = self.soup.select_one('table.product-props')
        if not table_soup:
            return None
        for td_soup in table_soup.select('tbody>tr>td'):
            if 'Общее впечатление:' == td_soup.text:
                return td_soup.next.next.next.next.text
            if '{}:'.format(title) == td_soup.text:
                return td_soup.next.next.next.text

    def _get_info_company(self, soup):
        self.rating.average_rating = self._convert_string_to_float(
            soup.select_one('div.product-header-left>'
                            'div.product-header-rating-row'
                            '>abbr.rating').attrs['title'])
        self.title = soup.select_one('h1.product-name>span.fn').text
        self.rating.price = self._get_company_rating('Цены')
        self.rating.quality = self._get_company_rating('Качество')
        self.rating.staff = self._get_company_rating('Персонал')
        self.rating.passage = self._get_company_rating('Проезд')
        self.rating.advertising = self._get_company_rating('Реклама')

        self.count = int(
            soup.select_one('span.reviews-counter>span>span.votes').text)

    def _get_company_rating(self, title):
        try:
            return self._convert_string_to_float(
                self.soup.find('div',
                               class_=['rating-item', 'tooltip-top', 'hover-brace'],
                               title=re.compile(title))
                    .select_one('div>div.rating-bg>div.rating-fill').attrs['style'])
        except AttributeError:
            return None

    @staticmethod
    def _convert_string_to_float(text):
        try:
            return float(text)
        except ValueError:
            return float(re.findall("\d+\.\d+", text)[0])

    @staticmethod
    def _convert_string_to_int(text):
        try:
            return int(text)
        except ValueError:
            return int(re.findall("\d+", text)[0])

    @staticmethod
    def _get_ids_of_reviews(soup):
        reviews_soup = soup.find_all('div', class_='item', itemprop='review')
        for review_soup in reviews_soup:
            url = review_soup.find('meta', itemprop='url').attrs['content']
            yield int(re.search(r'\d+', url).group())

    def _get_page(self, page):
        time.sleep(2)
        url = '{}/{}'.format(self.reviews_url, page)
        self.logger.send_info(url)
        resp = self.request('GET', url)

        if not resp.status_code == 200:
            self.logger.send_error(resp.text)
            raise Exception(resp.text)
        return self.soup

    def _captcha(self, soup, url):
        img_url = soup.select_one('form>table>tr>td[align="left"]>img')['src']
        r = self.session.request('GET', urljoin(self.BASE_URL, img_url),
                                 stream=True)
        if r.status_code == 200:
            with open('captcha.png', 'wb') as f:
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)
            captcha_res = input('captcha.png : ')
            path = urlparse(url).path
            data = {'captcha_url': path,
                    'keystring3': captcha_res,
                    'action_capcha_ban': "     Я не робот!     "}
            self.request('POST', url,
                         data=data)
        else:
            self.logger.send_error('Can not load captcha')
            raise Exception('Can not load captcha')

    def request(self, method, url, **kwargs):
        time.sleep(2)
        resp = self.session.request(method, url, **kwargs)
        self.soup = BeautifulSoup(resp.text, 'html.parser')
        if self.soup.select_one('form>input[name="captcha_url"]'):
            if self.DEBUG:
                self._captcha(self.soup, url)
            else:
                raise CaptchaException()
        return resp


class Rating:
    average_rating = None
    price = None
    quality = None
    staff = None
    passage = None
    advertising = None
    min_scale = 1
    on_scale = 5

    def get_dict(self):
        return {
            'average_rating': self.average_rating,
            'price': self.price,
            'quality': self.quality,
            'staff': self.staff,
            'passage': self.passage,
            'advertising': self.advertising,
            'on_scale': self.on_scale,
        }


class Review:
    id = None
    title = None
    text = None
    like = None
    sub_reviews = None
    date = None
    rating = None
    ratings = []
    advantages = None
    disadvantages = None
    author = None
    overall_impression = None
    is_recommend_friends = None

    def __init__(self):
        self.rating = Rating()
        self.author = Author()
        self.comments = list()

    def get_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'text': self.text,
            'like': self.like,
            'sub_reviews': [item.get_dict() for item in self.sub_reviews],
            'rating': self.rating.get_dict(),
            'ratings': self.ratings,
            'advantages': self.advantages,
            'disadvantages': self.disadvantages,
            'author': self.author.get_dict(),
            'overall_impression': self.overall_impression,
            'is_recommend_friends': self.is_recommend_friends,
        }

    def get_text(self):
        return 'Комментарий: {}\n Плюсы: {}\n Минусы: {}'.format(
            self.text, self.advantages, self.disadvantages
        )


class Author:
    name = None
    reputation = None
    count_reviews = None
    location = None
    url = None
    year_visit = None
    country = None
    township = None
    district = None
    city = None
    street = None
    house = None

    def get_dict(self):
        return {
            'name': self.name,
            'reputation': self.reputation,
            'count_reviews': self.count_reviews,
            'location': self.location,
            'url': self.url,
            'year_visit': self.year_visit,
            'country': self.country,
            'township': self.township,
            'district': self.district,
            'city': self.city,
            'street': self.street,
            'house': self.house,
        }


class CaptchaException(Exception):
    pass


if __name__ == '__main__':
    prov = OtzovikCom('gostinica_volhov_russia_velikiy_novgorod')
    prov.start()
    for r in prov.reviews:
        print(r.get_dict())
