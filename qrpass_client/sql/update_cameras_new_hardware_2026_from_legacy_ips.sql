-- =============================================================================
-- Миграция со СТАРЫХ IP в БД (192.168.1.2 … .16 как у вас на скрине) на НОВУЮ схему.
-- Прежний файл update_cameras_new_hardware_2026.sql ищет в url уже .101–.115 — если в таблице
-- ещё старые адреса, получится «0 строк изменено».
--
-- Здесь: WHERE url LIKE '%@192.168.1.N:%' — сопоставление по порядку периметра:
--   .2 → .101 «Периметр 1», …, .16 → .115 «Периметр 15»
--
-- Дальше — INSERT камер, которых в старой БД не было (.31–.37, .51–.53, .71–.73), затем Rules.
-- Выполните целиком → Write Changes.
-- =============================================================================

-- =============================================================================
-- 1) Периметр: старый IP → новый URL + имя (15 строк)
-- =============================================================================

UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.101:554/1/1', name = 'Периметр 1' WHERE url LIKE '%@192.168.1.2:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.102:554/1/1', name = 'Периметр 2' WHERE url LIKE '%@192.168.1.3:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.103:554/1/1', name = 'Периметр 3' WHERE url LIKE '%@192.168.1.4:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.104:554/1/1', name = 'Периметр 4' WHERE url LIKE '%@192.168.1.5:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.105:554/1/1', name = 'Периметр 5' WHERE url LIKE '%@192.168.1.6:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.106:554/1/1', name = 'Периметр 6' WHERE url LIKE '%@192.168.1.7:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.107:554/1/1', name = 'Периметр 7' WHERE url LIKE '%@192.168.1.8:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.108:554/1/1', name = 'Периметр 8' WHERE url LIKE '%@192.168.1.9:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.109:554/1/1', name = 'Периметр 9' WHERE url LIKE '%@192.168.1.10:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.110:554/1/1', name = 'Периметр 10' WHERE url LIKE '%@192.168.1.11:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.111:554/1/1', name = 'Периметр 11' WHERE url LIKE '%@192.168.1.12:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.112:554/1/1', name = 'Периметр 12' WHERE url LIKE '%@192.168.1.13:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.113:554/1/1', name = 'Периметр 13' WHERE url LIKE '%@192.168.1.14:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.114:554/1/1', name = 'Периметр 14' WHERE url LIKE '%@192.168.1.15:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.115:554/1/1', name = 'Периметр 15' WHERE url LIKE '%@192.168.1.16:%';

-- =============================================================================
-- 2) Новые камеры (если строки ещё нет — добавим; повторный запрос не дублирует)
-- =============================================================================

INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.31:554/1/1', 'Б3. Вход 2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.31:%');
INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.32:554/1/1', 'Б3. Галерея' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.32:%');
INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.33:554/1/1', 'Б3. Сектор 1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.33:%');
INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.34:554/1/1', 'Б3. Сектор 2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.34:%');
INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.35:554/1/1', 'Б3. Сектор 3' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.35:%');
INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.36:554/1/1', 'Б3. Сектор 4' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.36:%');
INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.37:554/1/1', 'Б3. Выход' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.37:%');

INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.51:554/1/1', 'Б5. Вход 2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.51:%');
INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.52:554/1/1', 'Б5. Вход 1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.52:%');
INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.53:554/1/1', 'Б5. Сектор 4' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.53:%');

INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.71:554/1/1', 'Выход Б5' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.71:%');
INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.72:554/1/1', 'Галерея 1 Б5' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.72:%');
INSERT INTO Cameras (url, name)
SELECT 'rtsp://admin:smolpole2017@192.168.1.73:554/1/1', 'Галерея 2 Б5' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url LIKE '%@192.168.1.73:%');

-- =============================================================================
-- 3) Только Person — DELETE Rules (.31–.37, .51–.53, .71–.73)
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
-- 4) RED — color_id=2 для периметра .101–.115
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

-- Проверка: SELECT id, name, url FROM Cameras ORDER BY id;
