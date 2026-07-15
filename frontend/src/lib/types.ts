export type AgentLogEntry = {
  agent: string;
  output: Record<string, unknown>;
};

export type Suno = {
  product_name?: string;
  quantity?: number | null;
  cost_price_inr?: number | null;
  material?: string | null;
  category?: string;
  photo_ok?: boolean;
  photo_issue?: string | null;
  detected_language?: string;
  demo_fallback_used?: boolean;
};

export type Listing = {
  title?: string;
  description?: string;
  category?: string;
  keywords?: string[];
  maker_story?: string;
  appended_disclaimers?: string[];
};

export type Price = {
  selling_price_inr: number;
  margin_pct: number;
  discount_floor_inr: number;
  breakdown: { cost: number; shipping: number; overhead: number; margin_inr: number };
  within_typical_range: boolean;
  typical_range_inr?: [number, number] | null;
};

export type Compliance = {
  compliance_ok?: boolean;
  required_labels?: string[];
  required_licenses?: string[];
  gst_note?: string;
  required_label_text?: string;
  category_notes?: string;
};

export type Returns = {
  top_return_reason?: string;
  risk_level?: 'low' | 'medium' | 'high' | string;
  mitigations?: string[];
  needs_seller_confirmation?: boolean;
  confirmation_prompt?: string | null;
};

export type Packaging = {
  primary_pack?: string;
  outer_pack?: string;
  handling_note?: string;
  materials?: string[];
  shipping_label?: string | null;
  fragile?: boolean;
  perishable?: boolean;
};

export type Approval = { type: string; summary: string };

export type ProductAttributes = Record<string, string | number | string[] | null>;

export type ClarificationQuestion = { field: string; type: string; prompt: string };
export type Clarification = { kind: string; questions: ClarificationQuestion[] };

export type Authenticity = {
  verdict: 'ok' | 'review' | 'blocked' | string;
  flags?: string[];
  photo_authenticity?: string;
  note?: string | null;
};

export type RunResult = {
  id: string;
  status:
    | 'ready_for_approval'
    | 'needs_retake'
    | 'needs_clarification'
    | 'published'
    | 'rejected_by_seller'
    | string;
  reason?: string | null;
  clarification?: Clarification | null;
  authenticity?: Authenticity | null;
  suno?: Suno;
  product_attributes?: ProductAttributes | null;
  missing_attributes?: string[];
  listing?: Listing;
  price?: Price;
  compliance?: Compliance;
  returns?: Returns;
  packaging_plan?: Packaging;
  action_checklist?: string[];
  approvals?: Approval[];
  activity_log?: AgentLogEntry[];
};

/** Steps that are a re-do driven by one of the three self-correcting loops. */
export function isLoopStep(agent: string) {
  return /re-run|re-price|recheck|revise|re-review|size guide|return review/i.test(agent);
}

export function loopKind(agent: string): 'quality' | 'compliance' | 'returns' | null {
  if (/revise|re-review/i.test(agent)) return 'quality';
  if (/re-run|re-price|recheck/i.test(agent)) return 'compliance';
  if (/size guide|return review/i.test(agent)) return 'returns';
  return null;
}
