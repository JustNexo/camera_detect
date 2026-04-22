-- =============================================================================
-- Обновление RTSP и Rules (SQLite, users.db).
-- Имена камер в таблице могут быть любыми — отбор только по IP в url.
-- Шаблон '%@192.168.1.N:%' (с @ и двоеточием после последнего октета), чтобы .2
-- не совпадал с .20–.29 и т.п.
--
-- Формат url как в RTSP: rtsp://логин:пароль@IP:порт/...
-- Если у вас url без @ — замените условия вручную на id или другой шаблон.
--
-- DB Browser: Execute SQL → вставить → выполнить → Write Changes.
-- =============================================================================
--
-- Политика: RED → Rules (color_id=2, access_granted=1). Иначе → только Person (DELETE Rules).
-- color_id подставьте из Colors.

-- =============================================================================
-- 1) Новые RTSP
-- =============================================================================

UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.2:554/1/1'
  WHERE url LIKE '%@192.168.1.2:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.3:553/1/1'
  WHERE url LIKE '%@192.168.1.3:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.4:568/1/1'
  WHERE url LIKE '%@192.168.1.4:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.5:551/1/1'
  WHERE url LIKE '%@192.168.1.5:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.6:555/1/1'
  WHERE url LIKE '%@192.168.1.6:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.7:556/1/1'
  WHERE url LIKE '%@192.168.1.7:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.8:557/1/1'
  WHERE url LIKE '%@192.168.1.8:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.9:558/1/1'
  WHERE url LIKE '%@192.168.1.9:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.10:559/1/1'
  WHERE url LIKE '%@192.168.1.10:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.11:560/1/1'
  WHERE url LIKE '%@192.168.1.11:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.12:561/1/1'
  WHERE url LIKE '%@192.168.1.12:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.13:562/1/1'
  WHERE url LIKE '%@192.168.1.13:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.14:563/1/1'
  WHERE url LIKE '%@192.168.1.14:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.15:564/1/1'
  WHERE url LIKE '%@192.168.1.15:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.16:565/1/1'
  WHERE url LIKE '%@192.168.1.16:%';

UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.17:566/1/1'
  WHERE url LIKE '%@192.168.1.17:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.18:567/1/1'
  WHERE url LIKE '%@192.168.1.18:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.19:568/1/1'
  WHERE url LIKE '%@192.168.1.19:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.20:569/1/1'
  WHERE url LIKE '%@192.168.1.20:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.21:570/1/1'
  WHERE url LIKE '%@192.168.1.21:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.22:571/1/1'
  WHERE url LIKE '%@192.168.1.22:%';

UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.24:572/1/1'
  WHERE url LIKE '%@192.168.1.24:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.25:573/1/1'
  WHERE url LIKE '%@192.168.1.25:%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.26:574/1/1'
  WHERE url LIKE '%@192.168.1.26:%';

UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.28:575/1/1'
  WHERE url LIKE '%@192.168.1.28:%' AND url LIKE '%/1/1%';
UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.28:575/2/1'
  WHERE url LIKE '%@192.168.1.28:%' AND url LIKE '%/2/1%';

UPDATE Cameras SET url = 'rtsp://admin:smolpole2017@192.168.1.29:576/1/1'
  WHERE url LIKE '%@192.168.1.29:%';

-- =============================================================================
-- 2) Только Person — DELETE Rules
-- =============================================================================

DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.2:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.4:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.18:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.19:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.20:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.21:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.22:%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.28:%' AND url LIKE '%/1/1%' LIMIT 1);
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.28:%' AND url LIKE '%/2/1%' LIMIT 1);

-- =============================================================================
-- 3) RED — DELETE + INSERT color_id=2
-- =============================================================================

DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.3:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.3:%' LIMIT 1;

DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.5:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.5:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.6:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.6:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.7:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.7:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.8:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.8:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.9:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.9:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.10:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.10:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.11:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.11:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.12:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.12:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.13:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.13:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.14:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.14:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.15:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.15:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.16:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.16:%' LIMIT 1;

DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.17:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.17:%' LIMIT 1;

DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.24:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.24:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.25:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.25:%' LIMIT 1;
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.26:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.26:%' LIMIT 1;

DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url LIKE '%@192.168.1.29:%' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted)
SELECT id, 2, 1 FROM Cameras WHERE url LIKE '%@192.168.1.29:%' LIMIT 1;

-- Проверка:
-- SELECT id, name, url FROM Cameras ORDER BY url;
-- SELECT * FROM Rules ORDER BY camera_id;
