export type MercadoLibreSite = {
  id: string;
  country: string;
  currency: string;
};

export const MERCADO_LIBRE_SITES: MercadoLibreSite[] = [
  { id: "MLA", country: "阿根廷", currency: "ARS" },
  { id: "MBO", country: "玻利维亚", currency: "BOB" },
  { id: "MLB", country: "巴西", currency: "BRL" },
  { id: "MLC", country: "智利", currency: "CLP" },
  { id: "MCO", country: "哥伦比亚", currency: "COP" },
  { id: "MCR", country: "哥斯达黎加", currency: "CRC" },
  { id: "MRD", country: "多米尼加", currency: "DOP" },
  { id: "MEC", country: "厄瓜多尔", currency: "USD" },
  { id: "MSV", country: "萨尔瓦多", currency: "USD" },
  { id: "MGT", country: "危地马拉", currency: "GTQ" },
  { id: "MHN", country: "洪都拉斯", currency: "HNL" },
  { id: "MLM", country: "墨西哥", currency: "MXN" },
  { id: "MNI", country: "尼加拉瓜", currency: "NIO" },
  { id: "MPA", country: "巴拿马", currency: "USD" },
  { id: "MPY", country: "巴拉圭", currency: "PYG" },
  { id: "MPE", country: "秘鲁", currency: "PEN" },
  { id: "MLU", country: "乌拉圭", currency: "UYU" },
  { id: "MLV", country: "委内瑞拉", currency: "VES" },
];

export function currencyForSite(siteId: string) {
  return MERCADO_LIBRE_SITES.find((site) => site.id === siteId)?.currency ?? "";
}
