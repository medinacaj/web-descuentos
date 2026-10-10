-- Analista de Descuentos Chile — esquema Postgres (Supabase)
-- Idempotente: se puede ejecutar varias veces.

create extension if not exists pgcrypto;

-- Tipos ---------------------------------------------------------------------
do $$ begin
  create type source_kind as enum ('retail','banco','operador','caja','billetera','comparador','club','seguro','comunidad');
exception when duplicate_object then null; end $$;
do $$ begin
  create type source_frequency as enum ('daily','weekly');
exception when duplicate_object then null; end $$;
do $$ begin
  create type source_readable as enum ('ok','partial','blocked','unknown');
exception when duplicate_object then null; end $$;
do $$ begin
  create type item_condition as enum ('nuevo','reacondicionado','seminuevo','usado','exhibicion','importado');
exception when duplicate_object then null; end $$;
do $$ begin
  create type verify_status as enum ('confirmado','sin_confirmar','vencido');
exception when duplicate_object then null; end $$;
do $$ begin
  create type applies_to_me as enum ('te_aplica','te_aplicaria','no_te_aplica');
exception when duplicate_object then null; end $$;

-- Fuentes -------------------------------------------------------------------
create table if not exists sources (
  id            text primary key,                 -- slug estable, ej. 'falabella'
  name          text not null,
  kind          source_kind not null,
  base_url      text not null,
  frequency     source_frequency not null default 'daily',
  readable      source_readable not null default 'unknown',
  readable_cause text,                            -- 'js_dinamico', 'bloqueo_waf', 'login', 'robots', ...
  trust_rank    smallint not null default 5,      -- 1=tienda oficial ... 9=comunidad (orden de fuentes)
  only_hints    boolean not null default false,   -- agregadores/comunidades: solo pistas
  discovered_by text not null default 'manual',   -- 'manual' | 'auto'
  active        boolean not null default true,
  consecutive_failures int not null default 0,
  last_checked  timestamptz,
  created_at    timestamptz not null default now()
);

-- Productos -----------------------------------------------------------------
create table if not exists products (
  id             uuid primary key default gen_random_uuid(),
  name           text not null,
  brand          text,
  category       text,
  variant        jsonb not null default '{}'::jsonb,  -- {"model":"iPhone 15 Pro","storage_gb":256}
  min_storage_gb int,
  watch          boolean not null default false,
  target_price   numeric(12,0),                       -- CLP
  created_at     timestamptz not null default now()
);

-- Observaciones de precio -----------------------------------------------------
create table if not exists prices (
  id          bigserial primary key,
  product_id  uuid not null references products(id) on delete cascade,
  source_id   text not null references sources(id),
  seller      text,                                 -- vendedor real (≠ plataforma)
  seller_verified boolean,
  condition   item_condition not null,
  list_price  numeric(12,0),                        -- precio tachado (solo informativo, nunca referencia)
  price       numeric(12,0) not null,
  shipping    numeric(12,0),                        -- null = desconocido, 0 = gratis
  in_stock    boolean,
  url         text not null,
  raw         jsonb,                                -- extracto crudo para auditoría
  seen_at     timestamptz not null default now()
);
create index if not exists prices_product_seen_idx on prices (product_id, seen_at desc);
create index if not exists prices_source_seen_idx  on prices (source_id, seen_at desc);

-- Cupones -------------------------------------------------------------------
create table if not exists coupons (
  id             uuid primary key default gen_random_uuid(),
  source_id      text references sources(id),
  code           text,
  description    text,
  discount_type  text check (discount_type in ('percent','amount','shipping')),
  discount_value numeric(12,2),
  cap            numeric(12,0),
  min_purchase   numeric(12,0),
  valid_from     timestamptz,
  valid_to       timestamptz,
  status         verify_status not null default 'sin_confirmar',
  evidence_url   text,
  checked_at     timestamptz not null default now()
);

-- Beneficios (bancos, billeteras, operadores, cajas, clubes) -----------------
create table if not exists benefits (
  id            uuid primary key default gen_random_uuid(),
  issuer        text not null,                      -- 'BCI', 'Banco de Chile', 'MACH', ...
  card_type     text,                               -- 'credito' | 'debito' | 'prepago' | 'cualquiera'
  card_product  text,                               -- ej. 'Visa Signature'
  merchant      text,                               -- comercio o source_id
  channel       text,                               -- 'online' | 'presencial' | 'app' | 'todos'
  percent       numeric(5,2),
  cap           numeric(12,0),
  min_purchase  numeric(12,0),
  max_uses      int,
  weekdays      int[],                              -- ISO 1=lunes .. 7=domingo
  valid_from    date,
  valid_to      date,
  stackable     boolean,                            -- null = compatibilidad pendiente → no se suma
  is_cashback   boolean not null default false,
  exclusions    text,
  status        verify_status not null default 'sin_confirmar',
  terms_url     text,
  checked_at    timestamptz not null default now()
);

create table if not exists my_benefits (
  benefit_id uuid primary key references benefits(id) on delete cascade,
  applies    applies_to_me not null,
  note       text
);

-- Alertas enviadas ----------------------------------------------------------
create table if not exists alerts_sent (
  id          bigserial primary key,
  product_id  uuid references products(id),
  source_id   text references sources(id),
  condition   item_condition,
  price_final numeric(12,0) not null,
  sent_at     timestamptz not null default now(),
  reason      text not null                         -- 'nuevo_minimo', 'mejora_5pct', 'cruce_objetivo', ...
);
create index if not exists alerts_product_sent_idx on alerts_sent (product_id, sent_at desc);

-- Ejecuciones ---------------------------------------------------------------
create table if not exists runs (
  id             bigserial primary key,
  started_at     timestamptz not null default now(),
  finished_at    timestamptz,
  sources_ok     int not null default 0,
  sources_failed int not null default 0,
  notes          jsonb not null default '{}'::jsonb
);

-- Seguridad: el sistema usa la service key desde GitHub Actions; sin acceso anónimo.
alter table sources      enable row level security;
alter table products     enable row level security;
alter table prices       enable row level security;
alter table coupons      enable row level security;
alter table benefits     enable row level security;
alter table my_benefits  enable row level security;
alter table alerts_sent  enable row level security;
alter table runs         enable row level security;
