-- =============================================================================
-- Замена камер на объекте: новые RTSP и Rules (users.db).
-- ВНИМАНИЕ: если в Cameras ещё СТАРЫЕ IP (например 192.168.1.2–.16), этот файл даст «0 строк» —
-- используйте миграцию: update_cameras_new_hardware_2026_from_legacy_ips.sql
--
-- Источник: таблица объекта (периметр 101–115, прочие подсети .31–.37, .51–.53, .71–.73).
--
-- Контроль периметра: в старых исходниках отдельной таблицы/флага в БД нет — это режим
-- работы камер периметра; в SQLite по-прежнему только Colors/Rules (RED = красная форма).
-- Подсчёт животных / «трупов» в эту БД не входит — отдельная задача на клиенте, сюда не добавляли.
--
-- Политика здесь (проверьте столбец «Цвет одежды» в Excel и поправьте секцию 3 при расхождении):
--   • 192.168.1.101–115 — RED (периметр).
--   • Остальные IP из списка — только Person (DELETE Rules); если у вас там RED/BLUE иначе —
--     перенесите IP из блока «DELETE» в блок «RED» или наоборот.
--
-- Отбор камер: url LIKE '%@192.168.1.XXX:%' (трёхзначные октеты, без путаницы .10 / .101).
-- Имена: периметр 1–15; остальное — по смыслу таблицы (Б3/Б5). Если в вашем файле другие подписи
-- (например Дизбарьер, Санпропускник, КПП) — поправьте только поля name в секции 1.
-- DB Browser: Execute SQL → Write Changes.
-- =============================================================================

-- =============================================================================
-- 1) URL и имя на русском (колонка «Расположение» из файла; при расхождении поправьте name).
-- =============================================================================

UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.101:554/1/1', name = 'Периметр 1' WHERE url LIKE '%@192.168.1.101:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.102:554/1/1', name = 'Периметр 2' WHERE url LIKE '%@192.168.1.102:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.103:554/1/1', name = 'Периметр 3' WHERE url LIKE '%@192.168.1.103:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.104:554/1/1', name = 'Периметр 4' WHERE url LIKE '%@192.168.1.104:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.105:554/1/1', name = 'Периметр 5' WHERE url LIKE '%@192.168.1.105:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.106:554/1/1', name = 'Периметр 6' WHERE url LIKE '%@192.168.1.106:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.107:554/1/1', name = 'Периметр 7' WHERE url LIKE '%@192.168.1.107:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.108:554/1/1', name = 'Периметр 8' WHERE url LIKE '%@192.168.1.108:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.109:554/1/1', name = 'Периметр 9' WHERE url LIKE '%@192.168.1.109:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.110:554/1/1', name = 'Периметр 10' WHERE url LIKE '%@192.168.1.110:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.111:554/1/1', name = 'Периметр 11' WHERE url LIKE '%@192.168.1.111:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.112:554/1/1', name = 'Периметр 12' WHERE url LIKE '%@192.168.1.112:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.113:554/1/1', name = 'Периметр 13' WHERE url LIKE '%@192.168.1.113:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.114:554/1/1', name = 'Периметр 14' WHERE url LIKE '%@192.168.1.114:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.115:554/1/1', name = 'Периметр 15' WHERE url LIKE '%@192.168.1.115:%';

UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.31:554/1/1', name = 'Б3. Вход 2' WHERE url LIKE '%@192.168.1.31:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.32:554/1/1', name = 'Б3. Галерея' WHERE url LIKE '%@192.168.1.32:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.33:554/1/1', name = 'Б3. Сектор 1' WHERE url LIKE '%@192.168.1.33:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.34:554/1/1', name = 'Б3. Сектор 2' WHERE url LIKE '%@192.168.1.34:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.35:554/1/1', name = 'Б3. Сектор 3' WHERE url LIKE '%@192.168.1.35:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.36:554/1/1', name = 'Б3. Сектор 4' WHERE url LIKE '%@192.168.1.36:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.37:554/1/1', name = 'Б3. Выход' WHERE url LIKE '%@192.168.1.37:%';

UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.51:554/1/1', name = 'Б5. Вход 2' WHERE url LIKE '%@192.168.1.51:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.52:554/1/1', name = 'Б5. Вход 1' WHERE url LIKE '%@192.168.1.52:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.53:554/1/1', name = 'Б5. Сектор 4' WHERE url LIKE '%@192.168.1.53:%';

UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.71:554/1/1', name = 'Выход Б5' WHERE url LIKE '%@192.168.1.71:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.72:554/1/1', name = 'Галерея 1 Б5' WHERE url LIKE '%@192.168.1.72:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.73:554/1/1', name = 'Галерея 2 Б5' WHERE url LIKE '%@192.168.1.73:%';

-- =============================================================================
-- 2) Только Person — DELETE Rules (не периметр RED по умолчанию: .31–.37, .51–.53, .71–.73)
-- Подсчёт животных (.31, .51 в Excel) — не хранится в Rules; доработка клиента позже.
-- =============================================================================

DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.31:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.32:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.33:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.34:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.35:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.36:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.37:%' LIMIT 1);

DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.51:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.52:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.53:%' LIMIT 1);

DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.71:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.72:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.73:%' LIMIT 1);

-- =============================================================================
-- 3) RED — color_id=2 (замените при необходимости). Периметр 101–115.
-- =============================================================================

DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.101:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.101:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.102:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.102:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.103:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.103:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.104:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.104:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.105:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.105:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.106:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.106:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.107:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.107:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.108:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.108:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.109:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.109:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.110:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.110:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.111:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.111:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.112:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.112:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.113:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.113:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.114:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.114:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.115:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.115:%' LIMIT 1;

-- Проверка: SELECT id, name, url FROM Cameras ORDER BY url;
-- SELECT * FROM Rules ORDER BY camera_id;
