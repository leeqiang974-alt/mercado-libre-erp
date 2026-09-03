var config = {
    url: {
        //域名
        domain: function () {
            return "https://www.51selling.com";
        },
        //保存产品
        saveProduct: function () {
            return this.domain() + '/collect/CollectBox/Edit';
        },
        saveCollectProduct: function () {
            return this.domain() + '/collect/CollectBox/SaveProduct';
        },
        //上传图片
        uploadImage: function () {
            return this.domain() + '/File/UploadImageToOssByUrl';
        },
        //验证是否重复采集
        verifyDuplicate: function () {
            return this.domain() + '/collect/CollectBox/VerifyDuplicate';
        },
        //获取url采集数据
        getSourceUrlEntity: function () {
            return this.domain() + '/collect/CollectBox/GetSourceUrlEntity';
        },
        //获取最新版本号
        getChromeExtensionVersion: function () {
            return this.domain() + '/collect/CollectBox/GetChromeExtensionVersion';
        },
        //验证是否需要跳转到1688批发页面
        verifyRedirectedAlibaba: function () {
            return this.domain() + '/SellerSetting/VerifyRedirectedAlibaba';
        }
    },
    /*支持采集的平台,对象数组类型，方便后期拓展其他平台
    * MatchingURLs:数组类型，可匹配的URL，可多个
    * PlatformId:int类型，平台枚举(预留字段)
    * PlatformName: string类型，平台名称 */
    platformArr: [
        {
            MatchingURLs: [
                "https://www.wish.com/product/",
                "https://www.wish.com",
            ],
            PlatformId: 2,
            PlatformName: "Wish"
        },
        {
            MatchingURLs: [
                "https://*aliexpress.*/item/",
                "http://*aliexpress.*/item/"
            ],
            PlatformId: 3,
            PlatformName: "Aliexpress"
        },
        {
            //这里的配置不要动，否则会被读到其它速卖通站点中去  PlatformId: 3
            MatchingURLs: [
                "https://*aliexpress.ru/item/",
                "http://*aliexpress.ru/item/"
            ],
            PlatformId: 14,
            PlatformName: "AliexpressRus"
        },
        {
            MatchingURLs: [
                "https://*.amazon.*/*dp/",
                "https://*.amazon.*/*gp/",
                "https://*.amazon.*/*sspa/",
                "https://*.amazon.ie/*"
            ],
            PlatformId: 4,
            PlatformName: "Amazon"
        },
        {
            MatchingURLs: [
                "http://detail.1688.com/offer/",
                "https://detail.1688.com/offer/",
                "https://dj.1688.com/",
                "http://detail.m.1688.com/",
                "https://www.1688.com/mwb/detail.1688.com/offer/",
                "https://*.1688.com/page/offerlist",
                "https://aliance.1688.com/activity",
            ],
            PlatformId: 5,
            PlatformName: "Alibaba"
        },
        {
            MatchingURLs: [
                "https://*.alibaba.com/product",
                "https://www.alibaba.com/product-detail/",
                "https://*.alibaba.com/p-detail/"
            ],
            PlatformId: 6,
            PlatformName: "AlibabaInternation"
        },
        {
            MatchingURLs: [
                "https://www.joom.com/*/products/",
                "https://www.joom.ru/*/products/"
            ],
            PlatformId: 7,
            PlatformName: "Joom"
        }
        ,
        {
            MatchingURLs: [
                "https://item.taobao.com/item.htm",
                "https://srd.simba.taobao.com/rd",
                "https://click.simba.taobao.com/cc_im",
                "http://click.mz.simba.taobao.com/necpm",
                "https://click.mz.simba.taobao.com/necpm"
            ],
            PlatformId: 11,
            PlatformName: "TaoBao"
        }
        ,
        {
            MatchingURLs: [
                // "https://mobile.pinduoduo.com/goods.html",
                // "http://app.yangkeduo.com/",
                // "https://app.yangkeduo.com/",
                // "https://mobile.yangkeduo.com/",
                // "https://mobie.yangkeduo.com/",
                // "https://panduoduo.yangkeduo.com/",
                // "https://yangkeduo.com/*",
                // "https://pifa.pinduoduo.com/goods/detail/*"

                "http*//*pinduoduo*/*",
                "http*//*yangkeduo*/*"
            ],
            PlatformId: 12,
            PlatformName: "PinDuoDuo"
        },
        {
            MatchingURLs: [
                "https://www.ozon.ru/product",
                "https://ozon.kz/product",
                "https://ozon.by/product",
                "https://*.ozon.com/product"
            ],
            PlatformId: 8,
            PlatformName: "Ozon"
        }
        ,
        {
            MatchingURLs: [
                "https://www.lazada.co.id/products/",
                "https://www.lazada.vn/products/",
                "https://www.lazada.sg/products/",
                "https://www.lazada.com.my/products/",
                "https://www.lazada.co.th/products/",
                "https://www.lazada.com.ph/products/"
            ],
            PlatformId: 10,
            PlatformName: "Lazada"
        },
        {
            MatchingURLs: [
                "https://*.ebay.com/itm/",
                "https://*.ebay.com.au/itm/",
                "https://*.ebay.*/itm/",
                "https://*.ebay.*.*/itm/"
            ],
            PlatformId: 13,
            PlatformName: "Ebay"
        },
        {
            MatchingURLs: [
                "https://*.tmall.com/item.htm?*",
                "https://*.tmall.hk/hk/item.htm?*"
            ],
            PlatformId: 15,
            PlatformName: "Tmall"
        },
        {
            MatchingURLs: [
                "https://www.coupang.com/vp/products/*"
            ],
            PlatformId: 16,
            PlatformName: "CouPang"
        },
        {
            MatchingURLs: [
                "https://shopee.*/*",
                "https://*.xiapibuy.com/*"
            ],
            PlatformId: 9,
            PlatformName: "Shopee"
        },
        {
            MatchingURLs: [
                "https://item.jd.com/*",
                "https://item.m.jd.com/product/*",
                "http://item.jd.com/*",
                "http://item.m.jd.com/product/*"
            ],
            PlatformId: 18,
            PlatformName: "JD"
        },
        {
            MatchingURLs: [
                "https://*.walmart.com/ip/*",
                "https://*.walmart.ca/*",
                "https://*.walmart.com.mx/*",
            ],
            PlatformId: 19,
            PlatformName: "Walmart"
        },
        {
            MatchingURLs: [
                "https://*.banggood.com/*"
            ],
            PlatformId: 20,
            PlatformName: "Banggood"
        },
        {
            MatchingURLs: [
                "https://www.cdiscount.com/*"
            ],
            PlatformId: 17,
            PlatformName: "Cdiscount"
        },
        {
            MatchingURLs: [
                "https://*.temu.com/*"
            ],
            PlatformId: 21,
            PlatformName: "Temu"
        },
        {
            MatchingURLs: [
                "https://*.yiwugo.com/product/detail/*",
                "https://yiwugo.com/product/detail/*"
            ],
            PlatformId: 23,
            PlatformName: "Yiwugo"
        },
        {
            MatchingURLs: [
                "https://*.vvic.com/item/*",
                "https://vvic.com/item/*"
            ],
            PlatformId: 24,
            PlatformName: "VVic"
        },
        {
            MatchingURLs: [
                "https://*.sooxie.com/detail/*",
            ],
            PlatformId: 25,
            PlatformName: "Sooxie"
        },
        {
            MatchingURLs: [
                "https://*.dhgate.com/product/*",
            ],
            PlatformId: 26,
            PlatformName: "Dunhuang"
        },
        {
            MatchingURLs: [
                "https://*.mercadolibre.com.ve/*",
                "https://*.mercadolibre.com.uy/*",
                "https://*.mercadolibre.com.sv/*",
                "https://*.mercadolibre.com.pe/*",
                "https://*.mercadolibre.com.py/*",
                "https://*.mercadolibre.com.pa/*",
                "https://*.mercadolibre.com.ni/*",
                "https://*.mercadolibre.com.hn/*",
                "https://*.mercadolibre.com.gt/*",
                "https://*.mercadolibre.com.ec/*",
                "https://*.mercadolibre.com.do/*",
                "https://*.mercadolibre.co.cr/*",
                "https://*.mercadolivre.com.br/*",
                "https://*.mercadolibre.com.bo/*",
                "https://*.mercadolibre.com.ar/*",
                "https://*.mercadolibre.com.mx/*",
                "https://*.mercadolibre.*.*/*",
                "https://*.mercadolibre.*/*",
                "https://*.mercadolivre.*/*"
            ],
            PlatformId: 22,
            PlatformName: "Mercado"
        },
        {
            MatchingURLs: [
                "https://*.go2.cn/product/*",
                "http://*.go2.cn/product/*"
            ],
            PlatformId: 28,
            PlatformName: "TuGou"
        },
        {
            MatchingURLs: [
                "https://*.wsy.com/item.htm?*",
                "http://*.wsy.com/item.htm?*"
            ],
            PlatformId: 29,
            PlatformName: "WSY"
        },
        {
            MatchingURLs: [
                "https://*.etsy.com/*",
                "http://*.etsy.com/*"
            ],
            PlatformId: 30,
            PlatformName: "ETSY"
        },
        {
            MatchingURLs: [
                "https://*.onbuy.com/*",
                "http://*.onbuy.com/*"
            ],
            PlatformId: 27,
            PlatformName: "OnBuy"
        },
        {
            MatchingURLs: [
                "https://*.wildberries.ru/*",
                "https://*.wildberries.kg/*",
                "https://*.wildberries.by/*",
                "https://*.wildberries.am/*",
                "https://*.wb.ru/*"
            ],
            PlatformId: 35,
            PlatformName: "Wildberries"
        },
        {
            MatchingURLs: [
                "https://shop.tiktok.com/*",
                "https://*.tiktok.com/*",
                "https://shop-id.tokopedia.com/*",
                "https://shop-uk.tiktokw.eu/*"
            ],
            PlatformId: 32,
            PlatformName: "Tiktok"
        },
        {
            MatchingURLs: [
                "https://*.gigab2b.com/index.php?route=product/product*"
            ],
            PlatformId: 36,
            PlatformName: "GAIAB2B"
        },

        {
            MatchingURLs: [
                "https://*.shein.com/*-p-*.html*",
                "https://*shein*-p-*.html*",
                "https://*.shein.tw/*-p-*.html*",
                "https://*.shein.com.mx/*-p-*.html*",
                "https://*.shein.com.hk/*-p-*.html*"
            ],
            PlatformId: 38,
            PlatformName: "Shein"
        },
        {
            MatchingURLs: [
                "https://www.fruugo.es/*/p-*",
                "https://www.fruugo.us/*/p-*",
                "https://www.fruugo.de/*/p-*",
                "https://www.fruugo.it/*/p-*",
                "https://www.fruugo.fr/*/p-*",
                "https://www.fruugo.pt/*/p-*",
                "https://www.fruugo.jp/*/p-*",
                "https://www.fruugo.co.uk/*/p-*",
                "https://www.fruugoaustralia.com/*/p-*",
                "https://www.fruugochina.com/*/p-*",
                "https://www.fruugo.ie/*/p-*",
                "https://www.fruugo.pl/*/p-*",
            ],
            PlatformId: 39,
            PlatformName: "Fruugo"
        },
        {
            MatchingURLs: [
                "https://www.saleyee.cn/item/*",
                "https://www.saleyee.com/item/*",
            ],
            PlatformId: 41,
            PlatformName: "Saleyee"
        },
        {
            MatchingURLs: [
                "https://market.yandex.ru/product*",
                "https://market.yandex.ru/card*",
                "https://market.yandex.ru/pr*"
            ],
            PlatformId: 42,
            PlatformName: "Yandex"
        },
        {
            MatchingURLs: [
                "https://detail.91jf.com/goods/*"
            ],
            PlatformId: 43,
            PlatformName: "JF91"
        },
        {
            MatchingURLs: [
                "https://www.xiaohongshu.com/goods-detail/*"
            ],
            PlatformId: 44,
            PlatformName: "小红书"
        },
        {
            MatchingURLs: [
                "https://www.bao66.cn/p/*"
            ],
            PlatformId: 45,
            PlatformName: "BaoNiuNiu"
        },
        {
            MatchingURLs: [
                "https://www.17qcc.com/item/*"
            ],
            PlatformId: 46,
            PlatformName: "QingChuang"
        },
        {
            MatchingURLs: [
                "https://westmonth.com/products/*"
            ],
            PlatformId: 47,
            PlatformName: "WestMonth"
        },
        {
            MatchingURLs: [
                "https://haohuo.jinritemai.com/*"
            ],
            PlatformId: 49,
            PlatformName: "DouyinGoodStuff"
        },
        {
            MatchingURLs: [
                "https://www.doba.com/product/*"
            ],
            PlatformId: 51,
            PlatformName: "Doba"
        },
           {
            MatchingURLs: [
                "https://*.made-in-china.com/product/*"
            ],
            PlatformId: 54,
            PlatformName: "中国制造网"
        },
        {
            MatchingURLs: [
                "https://*.miravia.es/p/*"
            ],
            PlatformId: 55,
            PlatformName: "Miravia"
        },
        {
            MatchingURLs: [
                "https://www.arkswift.com/item/*"
            ],
            PlatformId: 59,
            PlatformName: "ArkSwift"
        },
    ],
    cookieName1: "usrid",
    cookieName2: "tk",
    logoBase64: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAACXBIWXMAAC4jAAAuIwF4pT92AAAFyGlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDggNzkuMTY0MDM2LCAyMDE5LzA4LzEzLTAxOjA2OjU3ICAgICAgICAiPiA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPiA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtbG5zOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIiB4bWxuczpzdEV2dD0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlRXZlbnQjIiB4bWxuczpkYz0iaHR0cDovL3B1cmwub3JnL2RjL2VsZW1lbnRzLzEuMS8iIHhtbG5zOnBob3Rvc2hvcD0iaHR0cDovL25zLmFkb2JlLmNvbS9waG90b3Nob3AvMS4wLyIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgMjEuMCAoV2luZG93cykiIHhtcDpDcmVhdGVEYXRlPSIyMDIxLTExLTA3VDIyOjMzOjA2KzA4OjAwIiB4bXA6TWV0YWRhdGFEYXRlPSIyMDIxLTExLTA3VDIyOjMzOjA2KzA4OjAwIiB4bXA6TW9kaWZ5RGF0ZT0iMjAyMS0xMS0wN1QyMjozMzowNiswODowMCIgeG1wTU06SW5zdGFuY2VJRD0ieG1wLmlpZDo2YWZkODg0Ni03MjhlLWZkNGMtYTZmMS03Y2E5NDFlOThiYTkiIHhtcE1NOkRvY3VtZW50SUQ9ImFkb2JlOmRvY2lkOnBob3Rvc2hvcDpiMGY5YTcyMy05ZDA1LTliNGQtOGU2MC03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",
};
var platformLinkRule = {
    'lazada.': {
        detail: function (url) {
            if (url.indexOf('/products') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'aliexpress.com': {
        detail: function (url) {
            if (url.indexOf('aliexpress.com/item/') !== -1 || url.indexOf('aliexpress.us/item/') !== -1 || url.indexOf('store/product') !== -1 || url.indexOf('aliexpress.com?spm') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    '1688.com': {
        detail: function (url) {
            if (url.indexOf('1688.com/page/index') !== -1 || url.indexOf('1688.com/offer') !== -1 || url.indexOf('1688.com/ci_bb') !== -1 || url.indexOf('1688.com/ci_king') !== -1 || url.indexOf('1688.com/activity') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            if (url.indexOf('1688.com/page/index') !== -1 || url.indexOf('1688.com/offer') !== -1 || url.indexOf('1688.com/ci_bb') !== -1 || url.indexOf('1688.com/ci_king') !== -1) {
                return "detail";
            }
            if (/page\/offerlist/.test(url)) {
                return "category"
            }
        }
    },
    'aliexpress.ru': {
        detail: function (url) {
            if (url.indexOf('aliexpress.ru/item/') !== -1 || url.indexOf('aliexpress.ru/store') !== -1 || url.indexOf('aliexpress.ru?spm') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'banggood.com': {
        detail: function (url) {
            if (url.indexOf('banggood.com/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'temu.com': {
        detail: function (url) {
            if (/-g-[0-9]*.html/.test(url) || (url.indexOf('goods.html') !== -1 && url.indexOf('goods_id') !== -1)) {
                return true;
            }
        },
        setUrl: function (url) {
            if (url.indexOf("temu.com") === -1) {
                if (url && url[0] != "/")
                    url = "/" + url;
                url = "www.temu.com" + url;
                if (!url.startsWith('http')) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'wish.com': {
        detail: function (url) {
            if (url.indexOf('wish.com/product') !== -1 || url.indexOf('wish.com/feed/tabbed_feed_latest/product') !== -1 || url.indexOf('wish.com/~/gadgets/camcorders/product/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'alibaba.com': {
        detail: function (url) {
            if (url.indexOf('www.alibaba.com/product-detail') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'walmart.ca': {
        detail: function (url) {
            if (url.indexOf('www.walmart.ca') !== -1) {
                return true;
            }
        },
        setUrl: function (url) {
            if (url.indexOf("walmart.ca") === -1) {
                url = "www.walmart.ca" + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'walmart.com': {
        detail: function (url) {
            if (url.indexOf('www.walmart.com/ip') !== -1 || url.indexOf('www.walmart.com.mx') !== -1) {
                return true;
            }
        },
        setUrl: function (url) {
            if (url.indexOf("walmart.com") === -1) {
                url = "www.walmart.com" + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'walmart.com.mx': {
        detail: function (url) {
            if (url.indexOf('www.walmart.com.mx') !== -1) {
                return true;
            }
        },
        setUrl: function (url) {
            if (url.indexOf("www.walmart.com.mx") === -1) {
                url = "www.walmart.com.mx" + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'tmall.com': {
        detail: function (url) {
            if (url.indexOf('tmall.com/item.htm') !== -1
                || url.indexOf('item.taobao.com/item.htm') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'tmall.hk': {
        detail: function (url) {
            if (url.indexOf('tmall.com/item.htm') !== -1
                || url.indexOf('item.taobao.com/item.htm') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'taobao.com': {
        detail: function (url) {
            if (url.indexOf('tmall.com/item.htm') !== -1
                || url.indexOf('item.taobao.com/item.htm') !== -1
                || url.indexOf('srd.simba.taobao.com/rd') !== -1
                || url.indexOf('click.simba.taobao.com/cc_im') !== -1
                || url.indexOf('click.mz.simba.taobao.com/necpm') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    // 'joom.com': {
    //     detail: function (url) {
    //         if (url.indexOf('/products') !== -1) {
    //             return true;
    //         }
    //     },
    //     getType: function (url) {
    //         return "detail";
    //     }
    // },
    // 'joom.ru': {
    //     detail: function (url) {
    //         if (url.indexOf('/products') !== -1) {
    //             return true;
    //         }
    //     },
    //     getType: function (url) {
    //         return "detail";
    //     }
    // },
    'yiwugo.com': {
        detail: function (url) {
            if (url.indexOf('/product/detail') !== -1) {
                return true;
            }
        }
        ,
        setUrl: function (url) {
            if (url.indexOf("yiwugo.com") === -1) {
                url = "www.yiwugo.com" + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'vvic.com': {
        detail: function (url) {
            if (url.indexOf('/item') !== -1) {
                return true;
            }
        }
        ,
        setUrl: function (url) {
            if (url.indexOf("vvic.com") === -1) {
                url = "www.vvic.com" + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'sooxie.com': {
        detail: function (url) {
            if (url.indexOf('/detail') !== -1) {
                return true;
            }
        }
        ,
        setUrl: function (url) {
            if (url.indexOf("sooxie.com") === -1) {
                url = "www.sooxie.com" + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'dhgate.com': {
        detail: function (url) {
            if (url.indexOf('/product') !== -1) {
                return true;
            }
        }
        ,
        setUrl: function (url) {
            if (url.indexOf("dhgate.com") === -1) {
                url = "www.dhgate.com" + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    // 'jd.com': {
    //     detail: function (url) {
    //         if (url.indexOf('item.jd.com/') !== -1 || url.indexOf('item.m.jd.com/product') !== -1) {
    //             return true;
    //         }
    //     },
    //     getType: function (url) {
    //         return "detail";
    //     }
    // },
    'shopee.': {
        detail: function (url) {
            if (url.indexOf('-i.') !== -1 || url.indexOf('product/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'tw.shopeesz.com': {
        detail: function (url) {
            if (url.indexOf('-i.') !== -1 || url.indexOf('product/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'xiapibuy.com': {
        detail: function (url) {
            if (url.indexOf('-i.') !== -1 || url.indexOf('product/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'mercadolibre': {
        detail: function (url) {
            if ((url.indexOf('&type=product&') !== -1 || url.indexOf('&type=item&') !== -1 || url.indexOf('=item_id:') !== -1 || url.indexOf('-_JM') !== -1) || url.indexOf('&wid=') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'mercadolivre': {
        detail: function (url) {
            if ((url.indexOf('&type=product&') !== -1 || url.indexOf('&type=item&') !== -1 || url.indexOf('=item_id:') !== -1 || url.indexOf('-_JM') !== -1)) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'go2.cn': {
        detail: function (url) {
            if (url.indexOf('/product/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'wsy.com': {
        detail: function (url) {
            if (url.indexOf('/item.htm') !== -1) {
                return true;
            } else {
                return false;
            }
        },
        setUrl: function (url) {
            if (url.indexOf("wsy.com") === -1) {
                url = "www.wsy.com" + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'etsy.com': {
        detail: function (url) {
            if (url.indexOf('/listing/') !== -1) {
                return true;
            } else { return false; }
        },
        setUrl: function (url) {
            if (url.indexOf("etsy.com") === -1) {
                url = "www.etsy.com" + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'onbuy.com': {
        detail: function (url) {
            if (/\/.*\/p\//.test(url)) {
                return true;
            } else { return false; }
        },
        setUrl: function (url) {
            if (url.indexOf("onbuy.com") === -1) {
                url = "www.onbuy.com" + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'amazon.': {
        detail: function (url) {
            if (url.indexOf('/dp/') !== -1 || url.indexOf('/gp/product/') !== -1 || url.indexOf('/sspa/') !== -1 || url.indexOf('ie/') !== -1) {
                return true;
            } else { return false; }
        },
        setUrl: function (url) {
            if (url.indexOf("amazon.") === -1) {
                url = "www.amazon." + url;
                if (url.indexOf("http") === -1) {
                    url = "https://" + url;
                }
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    },
    'wildberries.': {
        detail: function (url) {
            if (url.indexOf('/catalog') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'tiktok.com': {
        detail: function (url) {
            if (url.indexOf('/catalog') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'gigab2b.com': {
        detail: function (url) {
            if (url.indexOf('/index.php?route=product/product&product_id') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'fruugo.': {
        detail: function (url) {
            if (url.indexOf('/p-') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        },
    },
    'fruugoaustralia.': {
        detail: function (url) {
            if (url.indexOf('/p-') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'fruugochina.': {
        detail: function (url) {
            if (url.indexOf('/p-') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'shein.com': {
        detail: function (url) {
            if (url.indexOf('.shein') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'shein.tw': {
        detail: function (url) {
            if (url.indexOf('.shein') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        }
    },
    'saleyee.': {
        detail: function (url) {
            if (url.indexOf('/item/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        },
    },
    '91jf.': {
        detail: function (url) {
            if (url.indexOf('/goods/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        },
    },
    'yandex.ru': {
        detail: function (url) {
            if (url.indexOf('product-') !== -1 || url.indexOf('/card/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        },
    },
    'westmonth.com': {
        detail: function (url) {
            if (url.indexOf('products') !== -1 || url.indexOf('/overseas/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        },
    },
    'doba.com': {
        detail: function (url) {
            if (url.indexOf('/product/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        },
    },
    'made-in-china.com': {
        detail: function (url) {
            if (url.indexOf('/product/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        },
    },
    'miravia.es': {
        detail: function (url) {
            if (url.indexOf('/p/') !== -1) {
                return true;
            }
        },
        getType: function (url) {
            return "detail";
        },
    },
    'arkswift.com': {
        detail: function (url) {
            if (url.indexOf('/item/') !== -1) {
                return true;
            }
        },
        setUrl: function (url) {
            if (url.indexOf('arkswift.com') === -1) {
                if (url && url[0] != "/")
                    url = "/" + url;
                url = "https://www.arkswift.com" + url;
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        },
    },
    'ebay.': {
        detail: function (url) {
            // eBay商品详情页内禁用悬浮采集
            if (location.pathname.indexOf('/itm/') !== -1) {
                return false;
            }

            if (url.indexOf('/itm/') !== -1) {
                return true;
            }
        },
        setUrl: function (url) {
            if (url.indexOf("http") === -1) {
                url = location.origin + url;
            }
            return url;
        },
        getType: function (url) {
            return "detail";
        }
    }
}