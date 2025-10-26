{ pkgs }: {
     deps = [
       pkgs.python311
       pkgs.ffmpeg-full
     ];
   }
```
4. Нажмите **"Commit new file"**

### Файл 4: `.replit`

1. **"Add file"** → **"Create new file"**
2. Назовите файл: `.replit`
3. Вставьте:
```
   run = "python main.py"
   language = "python3"
   
   [nix]
   channel = "stable-23_11"
```
4. Нажмите **"Commit new file"**

---

## Шаг 3: Импорт в Replit

1. Перейдите на [replit.com](https://replit.com)
2. На главной странице найдите **"Create"** или **"+"**
3. Выберите **"Import from GitHub"** (может быть в выпадающем меню)
4. Вставьте URL вашего репозитория:
```
   https://github.com/l3lisscom-collab/podcast-bot
