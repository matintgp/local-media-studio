import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./e2e',timeout:120000,expect:{timeout:12000},use:{baseURL:process.env.STUDIO_E2E_URL||'http://127.0.0.1:5173',browserName:'chromium',channel:process.env.STUDIO_BROWSER_CHANNEL||undefined,headless:true},reporter:'list',workers:1});
