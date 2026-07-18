import type { ProductAttributes } from '@/lib/types';

// Friendly labels for the common attribute keys; anything else falls back to
// Title Case of the key, so a new field never renders as a raw snake_case string.
const LABELS: Record<string, string> = {
  color: 'Colour',
  net_quantity: 'Net Quantity',
  net_weight: 'Net Weight',
  country_of_origin: 'Country of Origin',
  gender: 'Gender',
  size: 'Size',
  fabric: 'Fabric',
  pattern: 'Pattern',
  occasion: 'Occasion',
  sleeve_length: 'Sleeve Length',
  type: 'Type',
  material: 'Material',
  product_type: 'Type',
  dimensions: 'Dimensions',
  finish: 'Finish',
  veg_nonveg: 'Veg / Non-Veg',
  food_type: 'Type',
  flavour: 'Flavour',
  shelf_life: 'Shelf Life',
  organic: 'Organic',
  container_type: 'Container Type',
  base_metal: 'Base Metal',
  purity: 'Purity',
  gross_weight: 'Gross Weight (g)',
  certification: 'Certification',
  plating: 'Plating',
  stone_type: 'Stone Type',
  sizing: 'Sizing',
  form: 'Form',
  skin_type: 'Suitable For',
  key_ingredients: 'Key Ingredients',
  fragrance: 'Fragrance',
  wax_type: 'Wax / Material',
  burn_time: 'Burn Time',
  age_group: 'Age Group',
  compartments: 'No. of Compartments',
  concern: 'Concern',
  pieces: 'Number of Items',
  pages: 'No. of Pages / Sheets',
  ruling: 'Ruling',
};

export function labelFor(key: string) {
  return LABELS[key] ?? key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

function valueFor(v: string | number | string[] | null) {
  if (Array.isArray(v)) return v.join(', ');
  return String(v);
}

export function ProductDetails({
  attributes,
  missing,
}: {
  attributes?: ProductAttributes | null;
  missing?: string[];
}) {
  if (!attributes) return null;

  const present = Object.entries(attributes).filter(
    ([, v]) => v !== null && v !== '' && !(Array.isArray(v) && v.length === 0),
  );
  if (present.length === 0 && (!missing || missing.length === 0)) return null;

  return (
    <section className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-5 py-3.5">
        <p className="text-[13px] font-bold text-ink">Product details</p>
        <span className="text-[11px] text-muted">as buyers will see on the marketplace</span>
      </div>

      <dl className="grid grid-cols-1 sm:grid-cols-2">
        {present.map(([key, v], i) => (
          <div
            key={key}
            className={`flex items-baseline gap-3 px-5 py-2.5 text-[13px] ${
              i % 2 === 0 ? 'sm:border-r sm:border-line' : ''
            } border-b border-line`}
          >
            <dt className="w-32 shrink-0 text-muted">{labelFor(key)}</dt>
            <dd className="font-medium text-ink">{valueFor(v)}</dd>
          </div>
        ))}
      </dl>

      {missing && missing.length > 0 && (
        <div className="border-t border-line bg-warn-bg/50 px-5 py-3.5">
          <p className="text-[12px] font-semibold text-warn">
            Add these details before publishing ({missing.length})
          </p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {missing.map((m) => (
              <span
                key={m}
                className="rounded-full border border-saffron/40 bg-surface px-2.5 py-1 text-[11px] font-medium text-warn"
              >
                {m}
              </span>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
