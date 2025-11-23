-- Migration: Add pain_points_opportunities field to processed_intelligence table
-- Date: 2025-11-22
-- Description: Adds a JSON field to store identified pain points and opportunities

-- Add the new column
ALTER TABLE processed_intelligence
ADD COLUMN pain_points_opportunities TEXT;

-- Set default empty value for existing records
UPDATE processed_intelligence
SET pain_points_opportunities = '{"pain_points": [], "opportunities": []}'
WHERE pain_points_opportunities IS NULL;
