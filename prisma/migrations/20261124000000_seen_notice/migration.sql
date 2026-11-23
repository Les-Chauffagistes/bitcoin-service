-- CreateTable
CREATE TABLE "seen_notice" (
    "id" UUID NOT NULL,
    "invoice_id" UUID NOT NULL,
    "txid" TEXT NOT NULL,
    "vout" INTEGER NOT NULL,
    "total_sats" BIGINT NOT NULL,
    "attempts" INTEGER NOT NULL DEFAULT 0,
    "next_attempt_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "last_status_code" INTEGER,
    "delivered_at" TIMESTAMPTZ(6),
    "failed_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "seen_notice_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "seen_notice_invoice_id_key" ON "seen_notice"("invoice_id");

-- CreateIndex
CREATE INDEX "seen_notice_next_attempt_at_idx" ON "seen_notice"("next_attempt_at");

-- AddForeignKey
ALTER TABLE "seen_notice" ADD CONSTRAINT "seen_notice_invoice_id_fkey" FOREIGN KEY ("invoice_id") REFERENCES "invoice"("id") ON DELETE RESTRICT ON UPDATE CASCADE;
