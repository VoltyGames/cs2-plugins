-- An admin holds one group, referenced by id. A name that matches no group is lost here; of
-- several groups, the one with the highest immunity is kept.
ALTER TABLE admins ADD COLUMN group_id BIGINT REFERENCES admin_groups(id) ON DELETE SET NULL;
UPDATE admins SET group_id = (
  SELECT g.id FROM admin_groups g
  WHERE admins.groups LIKE CONCAT('%"', g.name, '"%')
  ORDER BY g.immunity DESC, g.id DESC
  LIMIT 1
);
ALTER TABLE admins DROP COLUMN groups;

-- A server grant now replaces the admin's group on that server. SQLite cannot drop a column
-- inside a UNIQUE constraint, so the table is rebuilt through a copy.
CREATE TABLE admin_server_groups_copy (
  admin_steam_id BIGINT NOT NULL,
  server_tag VARCHAR(64) NOT NULL,
  group_id BIGINT NOT NULL,
  created_at BIGINT NOT NULL
);
INSERT INTO admin_server_groups_copy (admin_steam_id, server_tag, group_id, created_at)
SELECT s.admin_steam_id, s.server_tag, g.id, s.created_at
FROM admin_server_groups s
JOIN admin_groups g ON g.name = s.group_name
WHERE NOT EXISTS (
  SELECT 1 FROM admin_server_groups s2
  JOIN admin_groups g2 ON g2.name = s2.group_name
  WHERE s2.admin_steam_id = s.admin_steam_id
    AND s2.server_tag = s.server_tag
    AND (g2.immunity > g.immunity OR (g2.immunity = g.immunity AND g2.id > g.id))
);
DROP TABLE admin_server_groups;

CREATE TABLE IF NOT EXISTS admin_server_groups (
  id @ID@,
  admin_steam_id BIGINT NOT NULL,
  server_tag VARCHAR(64) NOT NULL,
  group_id BIGINT NOT NULL REFERENCES admin_groups(id) ON DELETE CASCADE,
  created_at BIGINT NOT NULL DEFAULT @NOW@,
  -- Leads with server_tag: the plugin loads every grant for its own server.
  UNIQUE (server_tag, admin_steam_id)
);
INSERT INTO admin_server_groups (admin_steam_id, server_tag, group_id, created_at)
SELECT admin_steam_id, server_tag, group_id, created_at FROM admin_server_groups_copy;
DROP TABLE admin_server_groups_copy;
