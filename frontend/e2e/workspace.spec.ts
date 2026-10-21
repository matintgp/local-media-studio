import {test,expect} from '@playwright/test';
import {mkdirSync} from 'node:fs';

test('Persian mock project, queue, gallery, composer, English switch',async({page})=>{
 mkdirSync('../docs/screenshots',{recursive:true});
 await page.goto('/');await expect(page.locator('html')).toHaveAttribute('dir','rtl');
 await page.getByRole('button',{name:'پروژه جدید'}).first().click();
 await page.locator('input[required]').fill('پروژه آزمایشی');
 await page.getByRole('button',{name:'ذخیره',exact:true}).click();
 await expect(page.getByRole('heading',{name:'ساخت مدیا'})).toBeVisible();
 await page.screenshot({path:'../docs/screenshots/create-fa.png',fullPage:true});
 await page.getByRole('button',{name:'افزودن به صف'}).click();
 await expect(page.getByText('DEMO / MOCK').first()).toBeVisible();
 await page.screenshot({path:'../docs/screenshots/queue-fa.png',fullPage:true});
 await expect(page.getByText('موفق').first()).toBeVisible({timeout:30000});
 await page.getByRole('button',{name:'کتابخانه'}).click();
 await expect(page.locator('.assetCard').first()).toBeVisible();
 await page.getByRole('button',{name:'استفاده مجدد'}).first().click();
 await expect(page.getByRole('button',{name:'ویدیو'})).toHaveClass(/active/);
 await page.getByRole('button',{name:'تدوین نهایی'}).click();
 await page.screenshot({path:'../docs/screenshots/composer-fa.png',fullPage:true});
 await page.getByRole('button',{name:'Switch language'}).click();
 await expect(page.locator('html')).toHaveAttribute('dir','ltr');
 await page.screenshot({path:'../docs/screenshots/composer-en.png',fullPage:true});
});
