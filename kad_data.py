import os.path
import sys

import cv2
import pytesseract
from playwright.sync_api import expect, sync_playwright, TimeoutError as PlaywrightTimeoutError, Error as PlayError


LINK = "secret"


def check_create_output_file():
    global to_continue

    if not os.path.exists(directory):
        os.makedirs(directory)

    if not os.path.isfile(file_name):
        with open(file_name, "a+", encoding="utf8") as f:
            f.write('District;Parcel;Status;inner_num;LinkID')
    else:
        to_continue = True


def get_next_line_num():
    with open(file_name, 'rb') as f:
        try:
            f.seek(-2, os.SEEK_END)
            while f.read(1) != b'\n':
                f.seek(-2, os.SEEK_CUR)
        except OSError:
            f.seek(0)
        last_line = f.readline().decode()
    try:
        next_num = int(last_line.split(';', 2)[1]) + 1
    except ValueError:
        next_num = 1
    return next_num


def get_keys(page):
    a_objects = page.locator("//center[1]//a[.//img]").all()
    data = []
    for e in a_objects:
        line = e.get_attribute("href")
        line = line.split("'", 2)[1].split("=", 1)[1]
        data.append(line)
    return data


def get_data(num):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        code_img = f"data/code_img_{district}.png"

        page.goto(f"{LINK}={district}")

        try:
            page.evaluate("""async () => {
                var st_img = document.getElementsByTagName('svg');
                st_img[0].removeChild(st_img[0].firstElementChild);
            }""")
        except PlayError:
            print('Capcha error / Wrong district')
            exit()

        svg_img = page.locator("\\svg")
        svg_img.screenshot(path=code_img)
        input_num = page.locator('//input[@id="ContentPlaceHolder1_txtBrParcele"]')
        input_code = page.locator('//input[@id="ContentPlaceHolder1_SVGCaptchaControl_CaptchaText"]')
        submit = page.locator('//input[@id="ContentPlaceHolder1_btnSubmit"]')

        # pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
        pytesseract.pytesseract.tesseract_cmd = 'tesseract'
        img = cv2.imread(code_img)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        code = pytesseract.image_to_string(img)
        code = code.strip()
        os.remove(code_img)

        err_num = page.locator('//div[@id="ContentPlaceHolder1_ValidationSummary1"]')

        input_num.fill(f'{num}')
        input_code.fill(code)
        submit.click()

        try:
            page.wait_for_event('response', timeout=3000)
        except PlaywrightTimeoutError:
            status = -1
            data = ''
            return status, data

        try:
            expect(err_num).to_be_hidden(timeout=1000)
        except AssertionError:
            # WRONG CAPCHA CODE
            status = -1
            data = ''
            return status, data

        land_data = page.locator('//table[@id="ContentPlaceHolder1_GridView1"]')
        try:
            expect(land_data).to_be_visible(timeout=1000)
        except AssertionError:
            # NO DATA
            status = 0
            data = ''
            return status, data

        paginator = page.locator('//tr[@class="pager"]')
        pager_exist = False

        try:
            expect(paginator).to_be_visible(timeout=100)
            pager_exist = True
        except AssertionError:
            pass

        count = 0
        if pager_exist:
            pages = paginator.locator('//a').all()
            count = len(pages)

        data = []
        for e in range(-1, count):
            if e >= 0:
                pages[e].click()
                try:
                    page.wait_for_event('response', timeout=3000)
                except PlaywrightTimeoutError:
                    status = -1
                    data = ''
                    return status, data
            try:
                page_data = get_keys(page)
            except PlaywrightTimeoutError:
                status = -1
                data = ''
                return status, data
            for _ in page_data:
                data.append(_)

        status = 1
        return status, data


def main_controller():
    global start_number
    global start_num_provided
    global to_continue

    if not start_num_provided and to_continue:
        start_number = get_next_line_num()

    no_data_count = 0
    while no_data_count < 20:
        d_status = -1
        while d_status < 0:
            d_status, d_data = (get_data(start_number))
        if d_status == 0:
            no_data_count += 1
        elif d_status > 0:
            no_data_count = 0

        with open(file_name, "a+", encoding="utf8") as f:
            if d_status < 1:
                f.write(f'\n{district};{start_number};{d_status};0;{d_data}')
            else:
                for idx, line in enumerate(d_data, start=1):
                    f.write(f'\n{district};{start_number};{d_status};{idx};{line}')

        if (start_number % 25) == 0:
            print(f"Processed {start_number} lines")
        start_number += 1

    print('END. Looks like there is no more data')


def error_quit(msg):
    print(f'ERROR. {msg}')
    exit()


if __name__ == '__main__':
    start_number = 1
    to_continue = False
    start_num_provided = False

    try:
        district = sys.argv[1]
    except IndexError:
        error_quit('No district provided')

    try:
        start_number = int(sys.argv[2])
    except IndexError:
        pass
    except ValueError:
        error_quit('Invalid data provided')

    if start_number < 1:
        error_quit('Invalid data provided')
    if start_number > 1:
        start_num_provided = True

    directory = "data"
    file_name = f'{directory}/output_{district}.csv'
    try:
        check_create_output_file()
        main_controller()
    except KeyboardInterrupt:
        print('END. Interrupted')
        exit()
