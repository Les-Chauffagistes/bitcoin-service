-- AlterTable
ALTER TABLE "scan_cursor" ADD COLUMN     "lease_owner" TEXT,
ADD COLUMN     "lease_until" TIMESTAMPTZ(6),
ALTER COLUMN "last_block_hash" DROP NOT NULL,
ALTER COLUMN "last_block_height" DROP NOT NULL;

-- AlterTable
ALTER TABLE "webhook_delivery" DROP COLUMN "attempt",
DROP COLUMN "error",
DROP COLUMN "status_code",
ADD COLUMN     "attempts" INTEGER NOT NULL DEFAULT 0,
ADD COLUMN     "delivered_at" TIMESTAMPTZ(6),
ADD COLUMN     "fail_reason" TEXT,
ADD COLUMN     "failed_at" TIMESTAMPTZ(6),
ADD COLUMN     "last_error" TEXT,
ADD COLUMN     "last_status_code" INTEGER,
ALTER COLUMN "next_attempt_at" SET NOT NULL,
ALTER COLUMN "next_attempt_at" SET DEFAULT CURRENT_TIMESTAMP;

-- CreateIndex
CREATE UNIQUE INDEX "webhook_delivery_txid_vout_key" ON "webhook_delivery"("txid", "vout");

