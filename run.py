import os
import re
from typing import Any
import requests
import json
import time
import random

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class Auto(webdriver.Chrome):
    def __init__(self, driver_path=r"C:\\Users\\\u0415\u0433\u043e\u0440\\.cache\\selenium\\chromedriver\\win64\\109.0.5414.74\\chromedriver.exe", teardown=False):
        self.driver_path = driver_path
        self.teardown = teardown
        os.environ["PATH"] += os.pathsep + self.driver_path

        options = webdriver.ChromeOptions()
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-insecure-localhost")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument("--ignore-ssl-errors=yes")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-web-security")

        super(Auto, self).__init__(options=options)
        self.original_wait = 10
        self.implicitly_wait(self.original_wait)
        self.maximize_window()


class AutoReport:
    def __init__(self, driver):
        self.driver = driver
        self.new_data = []
        self.current_id = 1

    def scrape_listings(self) -> None:
        base_url = "https://www.truckscout24.de/transporter/gebraucht/kuehl-iso-frischdienst/renault"
        self.driver.get(base_url)
        print(f"Зашел на страницу {base_url}")

        try:
            # Работа со страницами
            pagination = self.driver.find_element(By.CSS_SELECTOR, "ul.pagination")
            page_links = pagination.find_elements(By.TAG_NAME, "a")

            last_page = int(page_links[-2].text)
            print(f"Общее количество страниц: {last_page}")

            for page_number in range(last_page):
                page_url = f"{base_url}?page={page_number + 1}"
                self.driver.get(page_url)
                print(f"Зашел на страницу {page_url}")
                
                # Работа с объявлениями
                listings = self.get_listings()

                if listings:
                    random_listing_url = random.choice(listings)
                    self.driver.get(random_listing_url)
                    time.sleep(2)
                    print(f"Перешли на случайную ссылку: {random_listing_url}")

                    # Начало парсинга данных
                    print("Сбор данных")
                    self.get_images(self.current_id)
                    building_data = self.extract_auto_data()
                    self.new_data.append(building_data)

                    self.driver.back()
                    time.sleep(2)
                else:
                    print(f"На странице {page_url} не найдено ссылок на авто")

        except Exception as e:
            print(f"Ошибка при обработке страницы: {e}")

        self.save_results()

    # Собираем ссылки на объявления 
    def get_listings(self) -> list[str]:
        try:
            container = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'col.mt-0.d-flex.flex-column.row-gap-3'))
            )
            grid_bodies = container.find_elements(By.CLASS_NAME, 'grid-body')

            links = []
            for grid_body in grid_bodies:
                try:
                    link_element = grid_body.find_element(By.CSS_SELECTOR, 'a.d-flex.flex-column.text-decoration-none.mb-2')
                    link = link_element.get_attribute('href')

                    if link:
                        links.append(link)
                except Exception as e:
                    print(f"Не удалось обработать grid-body: {e}")

            return links

        except Exception as e:
            print(f"Произошла ошибка: {e}")
            return []

    # Извлекаем данные и добавляем в словарь
    def extract_auto_data(self) -> dict[str, Any]:
        auto_data = {
            "id": self.current_id,
            "href": self.get_href(),
            "title": self.get_title(),
            "price": self.get_price(),
            "mileage": self.get_mileage(),
            "color": self.get_color(),
            "power": self.get_power(),
            "description": self.get_description(),
            "phone": self.get_phone()
        }
        self.current_id += 1
        return auto_data

    # Абсолютная ссылка на объявление
    def get_href(self) -> str:
        return self.driver.current_url

    # Название
    def get_title(self) -> str:
        try:
            container = self.driver.find_element(By.ID, "inserat-titel")
            brand = container.find_element(By.CSS_SELECTOR, "b.word-break").text.strip()
            remaining_text = container.text.strip().split(brand, 1)[-1].strip()
            title_text = f"{brand} {remaining_text}"

            return title_text

        except Exception as e:
            print(f"Ошибка при извлечении заголовка: {e}")
            return ""

    # Цена
    def get_price(self) -> int:
        try:
            price_element = self.driver.find_element(By.CSS_SELECTOR, "div.fs-5.max-content.my-1.word-break.fw-bold")
            price_text = price_element.text.strip().replace("\u00a0", "").replace("\u20ac", "").replace(",", ".")
            price_value = int(float(price_text) * 1000)

            return price_value

        except Exception as e:
            print(f"Ошибка при извлечении цены: {e}")
            return 0

    # Пробег
    def get_mileage(self) -> int:
        mileage_str = self._get_property_value("Kilometerstand:")

        if mileage_str:
            mileage = int(''.join(filter(str.isdigit, mileage_str)))
            return mileage
        
        return 0

    # Цвет
    def get_color(self) -> str:
        return self._get_property_value("Farbe:") or ""

    # Мощность в kW
    def get_power(self) -> int:
        power_str = self._get_property_value("Leistung:")

        if power_str:
            match = re.match(r"(\d+)", power_str)
            if match:
                return int(match.group(1))
            
        return 0

    # Полное описание
    def get_description(self) -> str:
        try:
            properties_div = self.driver.find_element(By.ID, "description")
            container = properties_div.find_element(By.CSS_SELECTOR, "div.card-body.word-break.pt-2.pb-3")
            description_div = container.find_element(By.CSS_SELECTOR, "div.col.beschreibung")

            return description_div.text or ""
        
        except Exception as e:
            print(f"Ошибка при извлечении описания: {e}")
            return ""

    # Полный номер телефона дилера
    def get_phone(self) -> str:
        try:
            properties_div = self.driver.find_element(By.ID, "dealer")
            container = properties_div.find_element(By.CSS_SELECTOR, "div.card-body.word-break.pt-2.pb-3")
            phone_button = container.find_element(By.CSS_SELECTOR, "span.btn.btn-link.d-flex.align-items-center.mb-3.w-100.p-0.text-start")
            
            self.driver.execute_script("arguments[0].scrollIntoView(true);", phone_button)
            time.sleep(1)
            phone_button.click()
            time.sleep(2)
            phone_element = self.driver.find_element(By.CSS_SELECTOR, "ul.list-group.list-group-flush li i.fa-phone + a")

            return phone_element.get_attribute("href").replace("tel:", "")
        
        except Exception as e:
            print(f"Ошибка при извлечении телефона: {e}")
            return ""

    # Общий для пробег, цвет, мощность
    def _get_property_value(self, property_name: str) -> str | None:
        try:
            properties_div = self.driver.find_element(By.ID, "properties")
            container = properties_div.find_element(By.CSS_SELECTOR, "div.card-body.word-break.pt-2.pb-3")
            dls = container.find_elements(By.CSS_SELECTOR, "dl.d-flex.flex-column.flex-lg-row.border-bottom.my-2.p-0.pb-2")

            for dl in dls:
                dt = dl.find_element(By.CSS_SELECTOR, "dt.me-2.max-content").text.strip()
                if dt == property_name:
                    dd = dl.find_element(By.CSS_SELECTOR, "dd.m-0").text.strip()
                    return dd
            
            return None
        
        except Exception as e:
            print(f"Ошибка при извлечении свойства '{property_name}': {e}")
            return None

    # Изображения
    def get_images(self, auto_id: int) -> None:
        try:
            carousel = self.driver.find_element(By.CLASS_NAME, "keen-slider")
            slides = carousel.find_elements(By.CSS_SELECTOR, "div.keen-slider__slide.lazy__slide")
            
            image_urls = []

            for slide in slides:
                if len(image_urls) == 3:
                    self.save_images(image_urls, auto_id)
                    break
                
                try:
                    if slide.find_elements(By.TAG_NAME, "iframe"): # Проверка на видео
                        print("Найдено видео, пропускаем.")
                        continue
                    
                    if slide.find_elements(By.XPATH, "//button[contains(text(), 'Mehr Bilder anfragen')]"): # Проверка на наличие изображений
                        print("Изображений больше нет.")
                        break
                    
                    img = slide.find_element(By.TAG_NAME, "img")
                    src = img.get_attribute("src") or img.get_attribute("data-src")
                    
                    if src:
                        high_res_src = src.replace("vga", "hdv")  # Максимальное разрешение
                        image_urls.append(high_res_src)
                        print(f"Найдено изображение: {high_res_src}")
                    else:
                        print("Пустой src и data-src, пропускаем.")

                except Exception as e:
                    print(f"Ошибка при обработке slide: {e}")
        except Exception as e:
            print(f"Ошибка: {e}")

    # Сохраняем изображения
    def save_images(self, image_urls: list[str], auto_id: int) -> None:
        folder_name = "data"
        current_folder = os.path.join(folder_name, str(auto_id))

        if not os.path.exists(current_folder):
            os.makedirs(current_folder)

        for i, url in enumerate(image_urls):
            try:
                image_name = f"image_{i + 1}.jpg"
                image_path = os.path.join(current_folder, image_name)
                
                # Загружаем изображение по URL
                img_data = requests.get(url).content
                with open(image_path, 'wb') as f:
                    f.write(img_data)
                
                print(f"Изображение сохранено: {image_path}")
            except Exception as e:
                print(f"Ошибка при сохранении изображения {url}: {e}")

    # Сохраняем JSON
    def save_results(self) -> None:
        folder_name = "data"
        
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)

        json_data = {
            "ads": self.new_data
        }

        # Записываем обновленные данные в файл
        data_file_path = os.path.join(folder_name, "data.json")
        with open(data_file_path, "w", encoding="utf-8") as f:
            json.dump(json_data, f, ensure_ascii=False, indent=4)

        print(f"Результаты сохранены в {data_file_path}")


if __name__ == "__main__":
    with Auto(teardown=True) as bot:
        report = AutoReport(bot)
        report.scrape_listings()
