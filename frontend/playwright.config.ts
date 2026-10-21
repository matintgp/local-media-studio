import { defineConfig } from '@playwright/test';
export default defineConfig({testDir:'./e2e',timeout:60000,expect:{timeout:12000},use:{baseURL:'http://127.0.0.1:5173',browserName:'chromium',headless:true},reporter:'list',workers:1});
