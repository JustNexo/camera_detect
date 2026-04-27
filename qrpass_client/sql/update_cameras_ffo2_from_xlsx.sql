-- Auto-generated from XLSX
-- Rules mapping:
--   RED -> color_id=<red-color-id>, access_granted=1
--   NOTRED/NOTERED -> color_id=<red-color-id>, access_granted=0
--   BLUE/other/empty -> no rows in Rules
BEGIN TRANSACTION;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.101:554/1/1', 'Периметр 1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.101:554/1/1');
UPDATE Cameras SET name = 'Периметр 1' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.101:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.101:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.101:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.102:554/1/1', 'Периметр 2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.102:554/1/1');
UPDATE Cameras SET name = 'Периметр 2' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.102:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.102:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.102:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.103:554/1/1', 'Периметр 3' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.103:554/1/1');
UPDATE Cameras SET name = 'Периметр 3' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.103:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.103:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.103:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.104:554/1/1', 'Периметр 4' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.104:554/1/1');
UPDATE Cameras SET name = 'Периметр 4' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.104:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.104:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.104:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.105:554/1/1', 'Периметр 5' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.105:554/1/1');
UPDATE Cameras SET name = 'Периметр 5' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.105:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.105:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.105:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.106:554/1/1', 'Периметр 6' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.106:554/1/1');
UPDATE Cameras SET name = 'Периметр 6' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.106:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.106:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.106:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.107:554/1/1', 'Периметр 7' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.107:554/1/1');
UPDATE Cameras SET name = 'Периметр 7' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.107:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.107:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.107:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.108:554/1/1', 'Периметр 8' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.108:554/1/1');
UPDATE Cameras SET name = 'Периметр 8' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.108:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.108:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.108:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.109:554/1/1', 'Периметр 9' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.109:554/1/1');
UPDATE Cameras SET name = 'Периметр 9' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.109:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.109:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.109:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.110:554/1/1', 'Периметр 10' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.110:554/1/1');
UPDATE Cameras SET name = 'Периметр 10' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.110:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.110:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.110:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.111:554/1/1', 'Периметр 11' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.111:554/1/1');
UPDATE Cameras SET name = 'Периметр 11' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.111:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.111:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.111:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.112:554/1/1', 'Периметр 12' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.112:554/1/1');
UPDATE Cameras SET name = 'Периметр 12' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.112:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.112:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.112:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.113:554/1/1', 'Периметр 13' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.113:554/1/1');
UPDATE Cameras SET name = 'Периметр 13' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.113:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.113:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.113:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.114:554/1/1', 'Периметр 14' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.114:554/1/1');
UPDATE Cameras SET name = 'Периметр 14' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.114:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.114:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.114:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.115:554/1/1', 'Периметр 15' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.115:554/1/1');
UPDATE Cameras SET name = 'Периметр 15' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.115:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.115:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.115:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.11:554/cam/realmonitor?channel=1&subtype=0', 'Б1.Вход1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.11:554/cam/realmonitor?channel=1&subtype=0');
UPDATE Cameras SET name = 'Б1.Вход1' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.11:554/cam/realmonitor?channel=1&subtype=0';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.11:554/cam/realmonitor?channel=1&subtype=0' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.11:554/cam/realmonitor?channel=1&subtype=0' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.12:554/1/1', 'Б1.Вход2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.12:554/1/1');
UPDATE Cameras SET name = 'Б1.Вход2' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.12:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.12:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.12:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.21:554/cam/realmonitor?channel=1&subtype=0', 'Б2.Вход1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.21:554/cam/realmonitor?channel=1&subtype=0');
UPDATE Cameras SET name = 'Б2.Вход1' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.21:554/cam/realmonitor?channel=1&subtype=0';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.21:554/cam/realmonitor?channel=1&subtype=0' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.21:554/cam/realmonitor?channel=1&subtype=0' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.22:554/1/1', 'Б2.Вход2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.22:554/1/1');
UPDATE Cameras SET name = 'Б2.Вход2' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.22:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.22:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.22:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.31:554/1/1', 'Б3.Вход1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.31:554/1/1');
UPDATE Cameras SET name = 'Б3.Вход1' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.31:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.31:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.31:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.32:554/1/1', 'Б3.Вход2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.32:554/1/1');
UPDATE Cameras SET name = 'Б3.Вход2' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.32:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.32:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.32:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.33:554/1/1', 'Б3.Галерея1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.33:554/1/1');
UPDATE Cameras SET name = 'Б3.Галерея1' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.33:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.33:554/1/1' LIMIT 1);

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.34:554/1/1', 'Б3.Сектор4' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.34:554/1/1');
UPDATE Cameras SET name = 'Б3.Сектор4' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.34:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.34:554/1/1' LIMIT 1);

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.35:554/1/1', 'Б3.Сектор1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.35:554/1/1');
UPDATE Cameras SET name = 'Б3.Сектор1' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.35:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.35:554/1/1' LIMIT 1);

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.36:554/1/1', 'Б3.Сектор2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.36:554/1/1');
UPDATE Cameras SET name = 'Б3.Сектор2' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.36:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.36:554/1/1' LIMIT 1);

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.37:554/1/1', 'Б3.Сектор3' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.37:554/1/1');
UPDATE Cameras SET name = 'Б3.Сектор3' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.37:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.37:554/1/1' LIMIT 1);

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.41:554/cam/realmonitor?channel=1&subtype=0', 'Б4.Вход1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.41:554/cam/realmonitor?channel=1&subtype=0');
UPDATE Cameras SET name = 'Б4.Вход1' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.41:554/cam/realmonitor?channel=1&subtype=0';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.41:554/cam/realmonitor?channel=1&subtype=0' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.41:554/cam/realmonitor?channel=1&subtype=0' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.42:554/1/1', 'Б4.Вход2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.42:554/1/1');
UPDATE Cameras SET name = 'Б4.Вход2' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.42:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.42:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.42:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.51:554/cam/realmonitor?channel=1&subtype=0', 'Б5.Вход1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.51:554/cam/realmonitor?channel=1&subtype=0');
UPDATE Cameras SET name = 'Б5.Вход1' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.51:554/cam/realmonitor?channel=1&subtype=0';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.51:554/cam/realmonitor?channel=1&subtype=0' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.51:554/cam/realmonitor?channel=1&subtype=0' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.52:554/1/1', 'Б5.Вход2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.52:554/1/1');
UPDATE Cameras SET name = 'Б5.Вход2' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.52:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.52:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.52:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.53:554/1/1', 'Б5.Галерея1' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.53:554/1/1');
UPDATE Cameras SET name = 'Б5.Галерея1' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.53:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.53:554/1/1' LIMIT 1);

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.53:554/2/1', 'Б5.Галерея2' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.53:554/2/1');
UPDATE Cameras SET name = 'Б5.Галерея2' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.53:554/2/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.53:554/2/1' LIMIT 1);

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.71:554/1/1', 'Дизбарьер' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.71:554/1/1');
UPDATE Cameras SET name = 'Дизбарьер' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.71:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.71:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 0 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.71:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.72:554/1/1', 'Санпропускник' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.72:554/1/1');
UPDATE Cameras SET name = 'Санпропускник' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.72:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.72:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.72:554/1/1' LIMIT 1;

INSERT INTO Cameras (url, name) SELECT 'rtsp://admin:smolpole2017@192.168.1.73:554/1/1', 'КПП' WHERE NOT EXISTS (SELECT 1 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.73:554/1/1');
UPDATE Cameras SET name = 'КПП' WHERE url = 'rtsp://admin:smolpole2017@192.168.1.73:554/1/1';
DELETE FROM Rules WHERE camera_id = (SELECT id FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.73:554/1/1' LIMIT 1);
INSERT INTO Rules (camera_id, color_id, access_granted) SELECT id, 2, 0 FROM Cameras WHERE url = 'rtsp://admin:smolpole2017@192.168.1.73:554/1/1' LIMIT 1;

COMMIT;
