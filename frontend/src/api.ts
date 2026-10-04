export interface HistoricalCase {
  case_id: string
  equipment_family: string
  equipment_type: string
  language: string
  customer_description: string
  technician_notes: string | null
  resolution_text: string | null
  parts_replaced: string[]
}

export interface EvidenceHit {
  case: HistoricalCase
  rrf_score: number
  source_ranks: Record<string, number>
  match_scope: 'equipment_type' | 'equipment_family'
}

export interface SearchResponse {
  query: string
  equipment_type: string
  hits: EvidenceHit[]
  used_family_fallback: boolean
  warnings: string[]
}

export async function searchCases(
  query: string,
  equipmentType: string,
): Promise<SearchResponse> {
  const response = await fetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      query,
      equipment_type: equipmentType,
      limit: 5,
      candidate_depth: 5,
    }),
  })

  if (!response.ok) {
    throw new Error('Search failed. Please check the service and try again.')
  }

  return response.json()
}