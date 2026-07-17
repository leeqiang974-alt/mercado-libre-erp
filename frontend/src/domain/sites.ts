export type MercadoLibreSite = {
  id: string;
  country: string;
  currency: string;
};

export const MERCADO_LIBRE_SITES: MercadoLibreSite[] = [
  { id: "MLA", country: "Argentina", currency: "ARS" },
  { id: "MBO", country: "Bolivia", currency: "BOB" },
  { id: "MLB", country: "Brazil", currency: "BRL" },
  { id: "MLC", country: "Chile", currency: "CLP" },
  { id: "MCO", country: "Colombia", currency: "COP" },
  { id: "MCR", country: "Costa Rica", currency: "CRC" },
  { id: "MRD", country: "Dominican Republic", currency: "DOP" },
  { id: "MEC", country: "Ecuador", currency: "USD" },
  { id: "MSV", country: "El Salvador", currency: "USD" },
  { id: "MGT", country: "Guatemala", currency: "GTQ" },
  { id: "MHN", country: "Honduras", currency: "HNL" },
  { id: "MLM", country: "Mexico", currency: "MXN" },
  { id: "MNI", country: "Nicaragua", currency: "NIO" },
  { id: "MPA", country: "Panama", currency: "USD" },
  { id: "MPY", country: "Paraguay", currency: "PYG" },
  { id: "MPE", country: "Peru", currency: "PEN" },
  { id: "MLU", country: "Uruguay", currency: "UYU" },
  { id: "MLV", country: "Venezuela", currency: "VES" },
];

export function currencyForSite(siteId: string) {
  return MERCADO_LIBRE_SITES.find((site) => site.id === siteId)?.currency ?? "";
}
