-- Migration 003: add role column to staff_users
-- Existing rows default to 'staff'; first admin is bootstrapped from env vars on startup.

ALTER TABLE staff_users ADD COLUMN role TEXT NOT NULL DEFAULT 'staff'
    CHECK (role IN ('admin', 'staff'));
