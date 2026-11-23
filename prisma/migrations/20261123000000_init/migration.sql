-- CreateTable
CREATE TABLE "invoice" (
    "id" UUID NOT NULL,
    "order_id" TEXT NOT NULL,
    "derivation_index" SERIAL NOT NULL,
    "address" TEXT NOT NULL,
    "amount_cents" BIGINT NOT NULL,
    "btc_price_eur_cents" BIGINT NOT NULL,
    "expected_sats" BIGINT NOT NULL,
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "invoice_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "received_output" (
    "txid" TEXT NOT NULL,
    "vout" INTEGER NOT NULL,
    "address" TEXT NOT NULL,
    "amount_sats" BIGINT NOT NULL,
    "first_seen_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "block_height" INTEGER,
    "block_hash" TEXT,
    "confirmations" INTEGER NOT NULL DEFAULT 0,
    "notified_at" TIMESTAMPTZ(6),

    CONSTRAINT "received_output_pkey" PRIMARY KEY ("txid","vout")
);

-- CreateTable
CREATE TABLE "webhook_delivery" (
    "id" UUID NOT NULL,
    "txid" TEXT NOT NULL,
    "vout" INTEGER NOT NULL,
    "attempt" INTEGER NOT NULL,
    "status_code" INTEGER,
    "error" TEXT,
    "next_attempt_at" TIMESTAMPTZ(6),
    "created_at" TIMESTAMPTZ(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "webhook_delivery_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "scan_cursor" (
    "id" INTEGER NOT NULL DEFAULT 1,
    "last_block_hash" TEXT NOT NULL,
    "last_block_height" INTEGER NOT NULL,

    CONSTRAINT "scan_cursor_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "invoice_order_id_key" ON "invoice"("order_id");

-- CreateIndex
CREATE UNIQUE INDEX "invoice_derivation_index_key" ON "invoice"("derivation_index");

-- CreateIndex
CREATE UNIQUE INDEX "invoice_address_key" ON "invoice"("address");

-- CreateIndex
CREATE INDEX "received_output_address_idx" ON "received_output"("address");

-- CreateIndex
CREATE INDEX "webhook_delivery_next_attempt_at_idx" ON "webhook_delivery"("next_attempt_at");

-- AddForeignKey
ALTER TABLE "received_output" ADD CONSTRAINT "received_output_address_fkey" FOREIGN KEY ("address") REFERENCES "invoice"("address") ON DELETE RESTRICT ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "webhook_delivery" ADD CONSTRAINT "webhook_delivery_txid_vout_fkey" FOREIGN KEY ("txid", "vout") REFERENCES "received_output"("txid", "vout") ON DELETE RESTRICT ON UPDATE CASCADE;

