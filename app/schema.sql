-- 供水管网故障隔离服务 schema（幂等，可重复执行）。
-- 管网版本号与导入标记保存在单行 network_meta 中。

CREATE TABLE IF NOT EXISTS nodes (
    code      VARCHAR(128) PRIMARY KEY,
    kind      VARCHAR(16) NOT NULL,
    name      VARCHAR(255),
    CONSTRAINT chk_nodes_kind CHECK (kind IN ('source', 'junction', 'sink'))
);

CREATE TABLE IF NOT EXISTS edges (
    code         VARCHAR(128) PRIMARY KEY,
    from_code    VARCHAR(128) NOT NULL REFERENCES nodes(code) ON DELETE RESTRICT,
    to_code      VARCHAR(128) NOT NULL REFERENCES nodes(code) ON DELETE RESTRICT,
    has_valve    BOOLEAN NOT NULL DEFAULT FALSE,
    valve_closed BOOLEAN NOT NULL DEFAULT FALSE,
    name         VARCHAR(255),
    CONSTRAINT chk_edges_valve CHECK (valve_closed = FALSE OR has_valve = TRUE)
);

CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(from_code);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(to_code);

CREATE TABLE IF NOT EXISTS network_meta (
    id          SMALLINT PRIMARY KEY DEFAULT 1,
    version     INTEGER NOT NULL DEFAULT 1,
    initialized BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT chk_meta_singleton CHECK (id = 1)
);

INSERT INTO network_meta (id, version, initialized)
VALUES (1, 1, FALSE)
ON CONFLICT (id) DO NOTHING;
