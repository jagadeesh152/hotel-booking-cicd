-- Idempotent schema + seed data. Safe to run on every start.
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE IF NOT EXISTS rooms (
    id          SERIAL PRIMARY KEY,
    room_number VARCHAR(10) NOT NULL UNIQUE,
    room_type   VARCHAR(20) NOT NULL CHECK (room_type IN ('standard', 'deluxe', 'suite')),
    price_night NUMERIC(8, 2) NOT NULL CHECK (price_night > 0)
);

CREATE TABLE IF NOT EXISTS reservations (
    id          SERIAL PRIMARY KEY,
    reference   VARCHAR(20) NOT NULL UNIQUE,
    room_id     INTEGER NOT NULL REFERENCES rooms (id),
    guest_name  VARCHAR(100) NOT NULL,
    guest_email VARCHAR(254) NOT NULL,
    check_in    DATE NOT NULL,
    check_out   DATE NOT NULL,
    status      VARCHAR(20) NOT NULL DEFAULT 'confirmed'
                CHECK (status IN ('confirmed', 'cancelled')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (check_out > check_in),
    -- The database itself guarantees no two confirmed bookings overlap for a room,
    -- even under concurrent requests. [check_in, check_out) lets same-day turnover work.
    CONSTRAINT no_overlapping_confirmed EXCLUDE USING gist (
        room_id WITH =,
        daterange(check_in, check_out, '[)') WITH &&
    ) WHERE (status = 'confirmed')
);

INSERT INTO rooms (room_number, room_type, price_night) VALUES
    ('101', 'standard', 80.00), ('102', 'standard', 80.00), ('103', 'standard', 80.00),
    ('104', 'standard', 80.00), ('105', 'standard', 80.00),
    ('201', 'deluxe', 130.00), ('202', 'deluxe', 130.00), ('203', 'deluxe', 130.00),
    ('301', 'suite', 220.00), ('302', 'suite', 220.00)
ON CONFLICT (room_number) DO NOTHING;
