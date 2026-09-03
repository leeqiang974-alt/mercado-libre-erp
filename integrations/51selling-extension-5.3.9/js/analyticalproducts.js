function AnalyticalProducts(platformId, content, tab, SourceUrl, funCallback) {
    switch (platformId) {
        case 2:
            try {
                AnalyticalWishProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Wish产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 3:
            try {
                AnalyticalAliexpressProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Aliexpress产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;

        case 4:
            try {
                AnalyticalAmazonProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Amazon产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 5:
            try {
                AnalyticalAlibabaProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "1688产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 6:
            try {
                AnalyticalAlibabaInternationProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "1688国际站产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 7:
            try {
                AnalyticalJoomProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Joom产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 8:
            try {
                AnalyticalOzonProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Ozon产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 17:
            try {
                AnalyticalCdiscountProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Cdiscount产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        /*case 9:
                try {
                    AnalyticalShopeeProducts(content, tab, SourceUrl,funCallback);
                } catch (error) {
                    funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Shopee产品解析失败!" + error.message }, tab, function (response) { });
                }
                break;*/
        case 10:
            try {
                AnalyticalLazadaProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Lazada产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 11:
            try {
                let productUrl = tab?.url;
                if (!productUrl)
                    productUrl = SourceUrl;
                let baseUrl = productUrl.split('?')[0];
                if (baseUrl.indexOf("taobao") > -1) {
                    AnalyticalTaoBaoProducts(content, tab, SourceUrl, funCallback);
                } else if (baseUrl.indexOf("tmall") > -1) {
                    AnalyticalTmallProducts(content, tab, SourceUrl, '', funCallback);
                } else {
                    AnalyticalTaoBaoProducts(content, tab, SourceUrl, funCallback);
                }

                // if (tab.url.indexOf("taobao.com/search") > -1) {
                //     AnalyticalTaoBaoProducts(content, tab, SourceUrl, funCallback);
                // } else if (/[?&]priceTId=/.test(SourceUrl) && !/id=[^&]+&mi_id=/.test(SourceUrl) && !verifyUrlParameters(SourceUrl, "eurl", "taobao.com")) {
                //     AnalyticalTmallProducts(content, tab, SourceUrl, '', funCallback);
                // } else {
                //     AnalyticalTaoBaoProducts(content, tab, SourceUrl, funCallback);
                // }
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "淘宝产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 12:
            try {
                AnalyticalPinDuoDuoProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "拼多多产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 13:
            try {
                AnalyticalEbayProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                console.log(error);
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Ebay产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 14:
            try {
                AnalyticalAliexpressRusProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Aliexpress产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 15:
            try {
                let productUrl = tab?.url;
                if (!productUrl)
                    productUrl = SourceUrl;
                let baseUrl = productUrl.split('?')[0];

                if (baseUrl.indexOf("taobao") > -1) {
                    AnalyticalTaoBaoProducts(content, tab, SourceUrl, funCallback);
                } else if (baseUrl.indexOf("tmall") > -1) {
                    AnalyticalTmallProducts(content, tab, SourceUrl, '', funCallback);
                } else {
                    AnalyticalTmallProducts(content, tab, SourceUrl, '', funCallback);
                }

                // if (isFromNewDetail(SourceUrl, 'jianhua') || isFromNewDetail(SourceUrl, 'newdetail')) {  //淘宝首页采集天猫
                //     AnalyticalTmallProducts(content, tab, SourceUrl, '', funCallback);
                // } else if (!/[?&]spm=/.test(SourceUrl) && !/[?&]priceTId=/.test(SourceUrl) && SourceUrl.indexOf("detail.tmall.com") < 0) {     //淘宝首页有时候没有spm则需要判断进入淘宝方法
                //     AnalyticalTaoBaoProducts(content, tab, SourceUrl, funCallback);
                // } else if (tab.url.indexOf("taobao.com/search") > -1) {
                //     AnalyticalTaoBaoProducts(content, tab, SourceUrl, funCallback);
                // } else { //天猫详情采集
                //     AnalyticalTmallProducts(content, tab, SourceUrl, '', funCallback);
                // }
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "天猫产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 16:
            try {
                AnalyticalCouPangProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "CouPang产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 9:
            try {
                if (content != "none" && content && content.isBathCollect === true) {
                    //后台采集
                    var shopeeApiUrlObj = getShopeeHtmlUrl2(SourceUrl)
                    content.apiUrl = shopeeApiUrlObj.v4Url;
                    content.isBathCollect = true;
                }
                AnalyticalShopeeProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Shopee产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 18:
            try {
                AnalyticalJDProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "京东产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        case 19: {
            try {
                AnalyticalWalmartProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "沃尔玛产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 20: {
            try {
                AnalyticalBanggoodProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "棒谷产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 21: {
            try {
                AnalyticalTemuProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Temu产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 23: {
            try {
                AnalyticalYiwugoProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "义乌购产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 24: {
            try {
                AnalyticalVVicProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "搜款网产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 25: {
            try {
                AnalyticalSooxieProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "搜鞋网产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 26: {
            try {
                AnalyticalDunhuangProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "敦煌网产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 22: {
            try {
                AnalyticalMercadoliProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Mercadoli产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 27: {
            try {
                AnalyticalOnBuyProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "OnBuy产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 28: {
            try {
                AnalyticalTuGouProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "途购网产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
          case 29: {
            try {
                AnalyticalWSYProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "网商园产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 30: {
            try {
                AnalyticalETSYroducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "网商园产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 35: {
            try {
                AnalyticalWildberriesProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "WB产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 32: {
            try {
                AnalyticalTiktokProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Tiktok产品解析失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 36: {
            try {
                AnalyticalGIGAB2BProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "GIGA产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 38: {
            try {
                AnalyticalSheinProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Shein产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 39: {
            try {
                AnalyticalFruugoroducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Fruugo产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 41: {
            try {
                AnalyticalSaleyeeProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Saleyee产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 42: {
            try {
                AnalyticalYandexProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Yandex产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 43: {
            try {
                AnalyticalJF91Products(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "91家纺产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 44: {
            try {
                AnalyticalRedBookProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "小红书产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 45: {
            try {
                AnalyticalBaoNiuNiuProductsNew(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "包牛牛产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 46: {
            try {
                AnalyticalQingChuang(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "青创网产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 47: {
            try {
                AnalyticalWestMonth(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "西之月产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 49: {
            try {
                AnalyticalDouyinGoodStuff(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "抖音好货产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 51: {
            try {
                AnalyticalDoba(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Doba产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
         case 54: {
            try {
                AnalyticalMadeInChina(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "MadeInChina产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 55: {
            try {
                AnalyticalMiravia(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Miravia产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        case 59: {
            try {
                AnalyticalArkSwiftProducts(content, tab, SourceUrl, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "ArkSwift产品解析失败！" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
        }
        default:
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "暂不支持此平台产品采集！" }, tab, function (response) { });
            funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            break;
    }
}

function isFromNewDetail(url, spmValue) {
    const urlObj = new URL(url);
    const spm = urlObj.searchParams.get('spm');
    return spm ? spm.includes(spmValue) : false;
}

function verifyUrlParameters(url, verifyParaName, verifyTxt) {
    const urlObj = new URL(url);
    const res = urlObj.searchParams.get(verifyParaName);
    return res ? res.includes(verifyTxt) : false;
}

function getShopeeHtmlUrl2(url) {
    let siteUrl = decodeURIComponent(url),
        urlHost = '',
        shopIdAndItemId = '',
        shopId = '',
        itemId = '';

    if (siteUrl.indexOf('https://') !== -1) {
        // if(siteUrl.indexOf('mall.shopee.') !== -1){
        //     urlHost = siteUrl.substring(siteUrl.indexOf('https://') + 13);
        // }else {
        urlHost = siteUrl.substring(siteUrl.indexOf('https://') + 8);
        // }
        urlHost = urlHost.substring(0, urlHost.indexOf('/'));
    } else if (siteUrl.indexOf('http://') !== -1) {
        // if(siteUrl.indexOf('mall.shopee.') !== -1){
        //     urlHost = siteUrl.substring(siteUrl.indexOf('http://') + 12);
        // }else {
        urlHost = siteUrl.substring(siteUrl.indexOf('http://') + 7);
        // }
        urlHost = urlHost.substring(0, urlHost.indexOf('/'));
    }
    if (siteUrl.indexOf('-i.') !== -1) {
        shopIdAndItemId = siteUrl.substring(siteUrl.indexOf('-i.') + 3);
        if (shopIdAndItemId.indexOf('/') !== -1) {
            shopIdAndItemId = shopIdAndItemId.substring(0, shopIdAndItemId.indexOf('/'));
        }
        shopId = shopIdAndItemId.substring(0, shopIdAndItemId.indexOf('.'));
        itemId = shopIdAndItemId.substring(shopIdAndItemId.indexOf('.') + 1);
    } else if (siteUrl.indexOf('/product/') !== -1) {
        shopIdAndItemId = siteUrl.substring(siteUrl.indexOf('/product/') + 9);
        shopId = shopIdAndItemId.substring(0, shopIdAndItemId.indexOf('/'));
        itemId = shopIdAndItemId.substring(shopIdAndItemId.indexOf('/') + 1);
        if (itemId.indexOf('/') !== -1) {
            itemId = itemId.replace('/', '');
        }
    }
    if (itemId.indexOf('?') !== -1) {
        itemId = itemId.split('?')[0];
    }
    var v2Url = 'https://' + urlHost + '/api/v2/item/get?itemid=' + itemId + '&shopid=' + shopId,
        v4Url = 'https://' + urlHost + '/api/v4/item/get?itemid=' + itemId + '&shopid=' + shopId,
        v0Url = 'https://' + urlHost + '/api/v0/shop/' + shopId + '/item/' + itemId + '/shipping_info_to_address';
    return {
        v4Url: v4Url,
        v2Url: v2Url,
        v0Url: v0Url
    }
}

function catchFuncallback(reason, funCallback) {
    var errorMsg = { "Type": "Alter", "MessageType": "error", "Message": "采集失败！若此错误频繁出现，请联系客服！" }
    if (reason && reason.message) {
        if (reason.message.indexOf("Failed to fetch") > -1) {
            errorMsg.Message = "采集URL错误，请检查采集URL能被正常访问！";
        } else {
            errorMsg.Message = reason.message;
        }
    }
    funCallback(errorMsg)
}

function AnalyticalWishProducts(content, tab, souceUrl, funCallback) {

    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    var model = {
        Html: '',
        SourcePlatform: 2,
        SouceUrl: souceUrl ? souceUrl : content.url
    };
    SaveLiknProduct(tab, model, funCallback);
}

function AnalyticalAliexpressRusProducts(content, tab, souceUrl, funCallback) {
    AnalyticalAliexpressProducts(content, tab, souceUrl, funCallback, true);
}

function AnalyticalAliexpressProducts(content, tab, souceUrl, funCallback, isRu = false) {
    if (souceUrl.indexOf("aliexpress.ru") > -1) {
        AnalyticalRuAliexpressProducts(content, tab, souceUrl, funCallback);
    } else {
        AnalyticalMainAliexpressProducts(content, tab, souceUrl, funCallback);
    }
}

//速卖通俄罗斯站点
function AnalyticalRuAliexpressProducts(content, tab, souceUrl, funCallback) {

    funCallback({ Type: "GetAjaxResult", Async: true, RequestMethod: "GET", RequestHeaders: {}, RequestUrl: souceUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "text", RequestData: {}, }, tab, function (response) {

        const productUrl = new URL(souceUrl);
        const productIdRegex = /\/item\/([0-9]+(?:_[0-9]+)?)(?:\.html|\?|\/|$)/;
        const productIdMatch = souceUrl.match(productIdRegex);

        if (!productIdMatch) {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "未在链接中找到有效的商品ID" }, tab, function (response) { });
        }

        let sourceId = 0;
        let productId = productIdMatch[1];

        if (productId.includes('_')) {
            // 如果有下划线，拆分为数组
            let rawIdArr = productId.split('_');
            sourceId = rawIdArr[0];
            productId = rawIdArr[1];
        }

        // 获取当前页面的URL
        // 获取sku_id参数
        const skuId = productUrl.searchParams.get('sku_id');
        let paraObj = {
            skuId,
            productId,
            sourceId
        }

        if (response.IsSuccess) {
            console.log(response.Data);
            var model = {
                Html: btoa(encodeURI(response.Data)),
                SourcePlatform: 14,
                SouceUrl: souceUrl,
            };

            let headerObj = {
                //"content-type": "application/json",
                "aer-url": souceUrl,
                "bx-v": "2.5.28"
            };

            let widgetUrl = "https://aliexpress.ru/widget?_bx-v=2.5.28&uuid=e1459484-97b0-4e41-a0be-e06fb8a0ff01";

            //使用此接口获取描述数据
            funCallback({ Type: "GetAjaxResult", Async: true, RequestMethod: "POST", RequestHeaders: headerObj, RequestUrl: widgetUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (widgetResponse) {
                if (widgetResponse.IsSuccess) {
                    let moreData = {
                        descHtml: widgetResponse?.Data?.widgets?.find(x => x.uuid == "e1459484-97b0-4e41-a0be-e06fb8a0ff01")?.state?.data?.html,
                        skuInfo: ""
                    }

                    funCallback({ "Type": "GetAliexpressRuData", "Paras": paraObj }, tab, function (response) {
                        if (response.skuInfo && response.skuInfo != "{}") {
                            moreData.skuInfo = response.skuInfo;
                            model.MoreData = JSON.stringify(moreData);
                            SaveLiknProduct(tab, model, funCallback);
                        } else {
                            model.MoreData = JSON.stringify(moreData);
                            SaveLiknProduct(tab, model, funCallback);
                        }
                    });
                } else {
                    SaveLiknProduct(tab, model, funCallback);
                }
            });
        }
        else {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "未能成功获取到数据源！若此错误频繁出现，请联系客服！" }, tab, function (response) { });
            // SaveLiknProduct(tab, model, funCallback);
        }
    });
}

//速卖通主站点
function AnalyticalMainAliexpressProducts(content, tab, souceUrl, funCallback, isRu = false) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    let tkStorageKey = 'wyysaliexpressh5tk';
    let usucStorage = 'wyysaliexpressh5aepusucf';
    let apiDomain = 'https://acs.aliexpress.com/';
    let sizeInfoApiDomain = 'https://www.aliexpress.com/';
    if (tab && tab.url && tab.url.indexOf('aliexpress.us') > -1) {
        apiDomain = 'https://acs.aliexpress.us/';
        sizeInfoApiDomain = 'https://www.aliexpress.us/';
    }
    else if (souceUrl && souceUrl.indexOf('aliexpress.ru') > -1) {
        apiDomain = 'https://acs.aliexpress.ru/';
        tkStorageKey = 'wyysaliexpressruh5tk';
        usucStorage = 'wyysaliexpressruh5aepusucf';
    }

    function ExcuteAliexpressProductData(tk, aepUsucF) {
        if (!tk)
            tk = '';
        if (tk.indexOf('_') > -1)
            tk = tk.split('_')[0];
        let url = new URL(souceUrl);

        let productId = url.pathname.replace('/item/', '').replace('.html', '').replace('.htm', '');
        const regex = /^\d+$/;
        if (!regex.test(productId)) {
            const regex = /\/item\/(\d+)\.html/;
            const match = url.pathname.match(regex);
            productId = match[1];
        }

        let country = 'US';
        let language = 'en';
        let currency = 'USD';
        let province = '';
        let city = '';

        if (aepUsucF && aepUsucF.length > 0) {
            function getAepUsucFValue(key) {
                var cookieRegExp = new RegExp(
                    '(.*&?' + key + '=)(.*?)(&.*|$)',
                );
                var matchArr = aepUsucF.match(cookieRegExp)
                return matchArr && matchArr[2] || '';
            }

            country = getAepUsucFValue('region') || 'US';
            if (country === 'CN')
                country = 'US';
            let locale = getAepUsucFValue('b_locale') || '';
            language = locale.split('_')[0] || 'en';
            currency = getAepUsucFValue('c_tp') || 'USD';
            province = getAepUsucFValue('province') || '';
            city = getAepUsucFValue('city') || '';
        }

        if (isRu) {
            language = "ru";
            currency = 'RUB';
            country = 'RU';
        }

        let lang = language + '_' + country;
        function queryStringToMap(str) {
            var ret = Object.create(null);
            try {
                str = str.trim().replace(/^(\?|#|&)/, '');
                if (!str) {
                    return ret;
                }
                str.split('&').forEach(function (param) {
                    var parts = param.replace(/\ /g, ' ').split('=');
                    var key = parts.shift();
                    var val = parts?.length > 0 ? parts.join('=') : undefined;
                    val = val === undefined ? null : decodeURIComponent(val);
                    ret[key] = val;
                });
            } catch (err) { }
            return ret;
        }
        let queryStringMap = queryStringToMap(url.search || '') || {};
        let htmlData = JSON.stringify({
            productId: productId,
            _lang: lang,
            _currency: currency,
            country: country,
            province: "",//province,
            city: "",//city,
            channel: queryStringMap['channel'] || '',
            pdp_ext_f: queryStringMap['pdp_ext_f'] || '',
            pdpNPI: '',//queryStringMap['pdp_npi'] || '',
            sourceType: queryStringMap['sourceType'] || '',
            clientType: 'pc',
            ext: JSON.stringify(Object.assign({}, {}))
        });
        let time = new Date().getTime();
        let dataSign = getTmallDataSign(tk, time, htmlData);
        let dataUrl = apiDomain + 'h5/mtop.aliexpress.pdp.pc.query/1.0/?jsv=2.5.1' +
            //let dataUrl = apiDomain + 'h5/mtop.aliexpress.itemdetail.pc.asyncPCDetail/1.0/?jsv=2.5.1' +
            '&appKey=12574478&t=' + time + '&sign=' + dataSign + '&api=mtop.aliexpress.pdp.pc.query' +
            '&v=1.0&isSec=0&ecode=0&timeout=10000&dataType=json&valueType=string' +
            '&ttid=2022%40taobao_litepc_9.17.0&AntiFlood=true&AntiCreep=true&preventFallback=true&type=json' +
            '&data=' + escape(htmlData);

        funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: dataUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
            if (response.IsSuccess && response?.Data?.data?.result?.GLOBAL_DATA?.globalData?.subject) {
                var data = response.Data;

                //接口请求不通使用页面数据采集
                if (content && content?.box && content?.box != {} && data?.data?.result?.GLOBAL_DATA?.globalData?.bigBossBanTip == "Sorry, this item's currently unavailable in your location.") {
                    SaveProduct(tab, { "Box": content.box.boxInfo, "BoxItem": content.box.variants }, funCallback);
                    return;
                }

                if (data == null || data.data == null || data.data == {} || data.data.result == undefined || data.data.result == null) {
                    //有验证码需滑动验证码
                    if (data &&
                        data.data &&
                        data.data.url &&
                        data.data.url != null) {
                        funCallback({ "Type": "ShowTmallVerifyBox", "BoxHtml": '<iframe src="' + data.data.url + '"' + ' style="width: 100%; height: 300px;" scrolling="auto" frameborder="0"></iframe>' }, tab, function (response) { });
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "速卖通采集被拦截！请滑动验证码！" }, tab, function (response) { });
                    } else {
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集数据为空，请稍后重试！" }, tab, function (response) { });
                    }

                    funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
                    return;
                }

                var model = {
                    Html: btoa(encodeURI(JSON.stringify(data.data))),
                    SourcePlatform: 3,
                    SouceUrl: souceUrl
                };

                var otherInfoUrl = `${sizeInfoApiDomain}aeglodetailweb/api/msite/item?productId=${productId}`;
                funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: otherInfoUrl, RequestContentType: "application/json", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
                    let otherInfo = "";
                    if (response.IsSuccess)
                        otherInfo = JSON.stringify(response.Data);

                    model.MoreData = otherInfo;
                    getDescriptionInfo();
                });
                function getDescriptionInfo() {
                    //请求完SKU信息，再继续请求图文描述，图文描述如果请求失败，可以忽略
                    try {
                        //request(data.data.data.productDescComponent.descriptionUrl, {
                        // request(data.data.result.DESC.pcDescUrl, {
                        //     method: "GET",
                        //     responseType: "text"
                        // }).then(detailResult => {
                        //     data.data.DetailedDescription = detailResult;
                        //     model.Html = btoa(encodeURI(JSON.stringify(data.data)));
                        //     GetAliexpressDescInfo(data.data, model);
                        // }).catch(reason => {
                        //     SaveLiknProduct(tab, model, funCallback);
                        // });

                        let descUrl = data.data.result.DESC.pcDescUrl;
                        fetch(descUrl, {
                            method: 'GET', // 指定请求方法为 GET
                            mode: 'cors'   // 允许跨域请求
                        })
                            .then(response => {
                                if (!response.ok) {
                                    throw new Error('Network response was not ok');
                                }
                                return response.text();
                            })
                            .then(detailResult => {
                                data.data.DetailedDescription = detailResult;
                                model.Html = btoa(encodeURI(JSON.stringify(data.data)));
                                SaveLiknProduct(tab, model, funCallback);
                            })
                            .catch(error => {
                                SaveLiknProduct(tab, model, funCallback);
                            });

                    } catch (e) {
                        SaveLiknProduct(tab, model, funCallback);
                    }
                }

            } else {
                //接口请求不通使用页面数据采集
                if (content && content?.box && content?.box != {}) {
                    SaveProduct(tab, { "Box": content.box.boxInfo, "BoxItem": content.box.variants }, funCallback);
                } else {
                    funCallback({ "Type": "Alter", "MessageType": "error", "Message": "速卖通采集被拦截！请刷新速卖通页面重试，或前往产品详情页进行采集！" }, tab, function (response) { });
                    funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
                }
            }
        });
    }

    //获取描述信息
    function GetAliexpressDescInfo(productData, model) {
        try {
            let descUrl = productData.result.DESC.nativeDescUrl;
            //请求描述图片
            request(descUrl, {
                method: "GET",
                responseType: "text"
            }).then(descResult => {
                productData.DescImage = descResult;
                model.Html = btoa(encodeURI(JSON.stringify(productData)));
                SaveLiknProduct(tab, model, funCallback);

            }).catch(reason => {
                SaveLiknProduct(tab, model, funCallback);
            });
        } catch (e) {
            SaveLiknProduct(tab, model, funCallback);
        }
    }

    //本地缓存Token获取速卖通产品（适用于批量采集）
    function ExcuteAliexpressProductDataByLocalTk() {
        chrome.storage.local.get([tkStorageKey, usucStorage], function (result) {
            let tk = result[tkStorageKey];
            let aepUsucF = result[usucStorage];
            ExcuteAliexpressProductData(tk, aepUsucF);
        });
    }

    funCallback({ "Type": "GetDocumentCookies", "NeedNameArr": ["_m_h5_tk", "aep_usuc_f"] }, tab, function (response) {
        if (response && response._m_h5_tk && response._m_h5_tk.length > 0) {
            ExcuteAliexpressProductData(response._m_h5_tk, response.aep_usuc_f);
        } else {
            chrome.storage.local.get([tkStorageKey], function (result) {
                let tk = result[tkStorageKey];
                if (!tk) {//凭据不存在就调用下接口，会自动刷新凭证
                    request(apiDomain + "h5/mtop.aliexpress.pdp.pc.query/1.0/?jsv=2.5.1&appKey=12574478&t=1704881502814", {
                        method: "GET",
                        responseType: "json"
                    }).then(data => {
                        ExcuteAliexpressProductDataByLocalTk();
                    }).catch(reason => {
                        ExcuteAliexpressProductDataByLocalTk();
                    });
                } else {
                    ExcuteAliexpressProductDataByLocalTk();
                }
            });
        }
    });
    return;
}

function AnalyticalYandexProducts(content, tab, souceUrl, funCallback) {
    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    //根据路径参数获取产品数据保存
    function AnalyzeYandexInfo(cardProductId, cardOskuId, cardBusinessId, cardVariantArr) {
        //cardVariantArr = cardVariantArr.filter(item => item.type === "image");
        funCallback({ "Type": "GetYandexData" }, tab, function (response) {
            if (!response?.data?.user?.sk)
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集数据错误，请检查采集URL能被正常访问!" }, tab, function (response) { });

            //获取Cookie数据
            function getMultipleCookies(url, cookieNames, callback) {
                let cookieValues = [];

                // 获取多个指定名称的 cookies
                cookieNames.forEach(function (cookieName, index) {
                    chrome.cookies.get({ url: url, name: cookieName }, function (cookie) {
                        if (cookie) {
                            cookieValues.push(cookie.name + "=" + cookie.value);  // 存储cookie名和值
                        }

                        // 当所有 cookies 都获取完毕后，执行回调函数
                        if (index === cookieNames.length - 1) {
                            callback(cookieValues.join('; '));  // 使用 ; 拼接成字符串
                        }
                    });
                });
            }
            let sk = response.data.user.sk; //

            let params = new URLSearchParams(new URL(souceUrl).search);
            let cpc = params.get('cpc') || '';  //
            let businessId = params.get('uniqueId') || '';  //
            let oskuId = params.get('sku') || '';  //

            let parts = souceUrl.split('?');

            let baseUrl = parts[0];
            let baseUrlParts = baseUrl.split('/');
            let productId = baseUrlParts[baseUrlParts.length - 1];  //
            let transitionSource = 'filters'; //

            let productIndex = souceUrl.indexOf('/product');
            let cardIndex = souceUrl.indexOf('/card');
            let path = '';  //
            if (productIndex !== -1) {
                path = souceUrl.slice(productIndex);
            }
            if (cardIndex !== -1) {
                path = souceUrl.slice(cardIndex);
            }
            let queryRrl = "https://market.yandex.ru/api/resolve/?r=src/resolvers/productPage/resolveProductCardRemote:resolveProductCardRemote&r=src/resolvers/productPage/resolveProductCardRemote:resolveProductCardRemote";
            let bodyObj = {};
            let bodyParams = [];

            if (cardProductId) {
                productId = cardProductId;
            }
            if (cardOskuId) {
                oskuId = cardOskuId;
            }
            if (cardBusinessId) {
                businessId = cardBusinessId;
            }

            let bodyParamObj = {
                businessId,
                transitionSource,
                oskuId,
                productId
            }
            if (cpc) {
                bodyParamObj.cpc = cpc;
            }
            let mainVariant = {};
            let imageList = [];
            let variantImageArr = [];
            let variantArr = [];
            let mainVariantPara = [];  //当前页面变体属性集合
            let propertyNames = [];
            let Parameters = [];
            let categoryId = "";
            bodyParams.push(bodyParamObj);
            bodyParams.push(bodyParamObj);
            bodyObj.params = bodyParams;
            bodyObj.path = path;

            let mainVariantDataType = 0;
            getMultipleCookies(souceUrl, ['skid', 'sessar', 'Session_id'], function (cookies) {
                let headerObj = {
                    "content-type": "application/json",
                    "sk": sk,
                    "cookie": cookies
                };

                funCallback({ Type: "GetAjaxResult", RequestMethod: "POST", RequestHeaders: headerObj, RequestUrl: queryRrl, RequestDataType: "json", RequestData: JSON.stringify(bodyObj) }, tab, function (response) {
                    if (response.IsSuccess && response?.Data?.results[0]) {
                        console.log('ddd', JSON.stringify(response?.Data?.results[0]));
                        mainVariant = response.Data.results[0];
                        let mainVariantKey = mainVariant.data.result;
                        let mainVariantKeyCard = {};
                        try {
                            mainVariantKeyCard = mainVariant.data.collections.productCardJumpTable[mainVariantKey];
                        } catch (e) { }

                        if (!mainVariantKeyCard || Object.keys(mainVariantKeyCard).length == 0) {
                            try {
                                mainVariantKeyCard = mainVariant.data.collections.unifiedJumpTable;
                                mainVariantDataType = 1;
                            } catch (e) { }
                        }

                        if (!mainVariantKeyCard || Object.keys(mainVariantKeyCard).length == 0) {
                            try {
                                mainVariantKeyCard = mainVariant.data.collections.jumpListShort[mainVariantKey];
                                mainVariantDataType = 2;
                            } catch (e) { }
                        }

                        let mainVariantPrice = 0;
                        try {
                            mainVariantPrice = mainVariant.data.collections.price[mainVariantKey];
                        } catch (e) { }

                        let fullDesc = "";
                        try {
                            fullDesc = mainVariant.data.collections.fullDescription[mainVariantKey].text
                        } catch (e) { }

                        let shortDesc = "";
                        try {
                            shortDesc = mainVariant.data.collections.shortDescription[mainVariantKey].text
                        } catch (e) { }

                        let mainVariantCardMeta = mainVariant.data.collections.productCardMeta[mainVariantKey];
                        let mainVariantSpecs = mainVariant?.data?.collections?.compactSpecs?.[mainVariantKey];
                        let mainVariantTitle = mainVariant?.data?.collections?.title?.[mainVariantKey] ?? "";
                        let mainVariantFullSpecs = mainVariant?.data?.collections?.fullSpecs?.[mainVariantKey];
                        let mainVariantModelSpecs = mainVariant?.data?.collections?.modelSpecs?.[mainVariantKey];

                        //产品属性
                        if (mainVariantSpecs?.specItems) {
                            mainVariantSpecs.specItems.forEach(item => {
                                if (item.value) {
                                    let para = {
                                        "Key": item.name.trim(),
                                        "Value": item.value.trim(),
                                    };

                                    //产品类目
                                    if (item.hasOwnProperty('transition')) {
                                        categoryId = item.transition.params.categoryId;
                                    }
                                    Parameters.push(para);
                                    mainVariantPara.push(para);
                                }
                            });
                        }

                        //产品类目
                        try {
                            let mainVariantId = mainVariant.data.result;
                            categoryId = mainVariant.data.collections.compose[mainVariantId].categoryId;
                        } catch (e) { }

                        //产品属性
                        if (mainVariantFullSpecs?.specItems) {
                            mainVariantFullSpecs.specItems.forEach(item => {
                                if (Parameters.filter(x => x.Key == item.name).length === 0) {
                                    if (item.name && item.value) {
                                        let para = {
                                            "Key": item.name.trim(),
                                            "Value": item.value.trim(),
                                        };
                                        Parameters.push(para);
                                    }
                                }
                            })
                        }

                        //产品属性
                        if (mainVariantModelSpecs?.specLines?.[0]?.groups) {
                            mainVariantModelSpecs.specLines[0].groups.forEach(group => {
                                group.items.forEach(item => {
                                    let para = {
                                        "Key": item.name.trim(),
                                        "Value": item.value.trim(),
                                    };
                                    Parameters.push(para);
                                })
                            });
                        }

                        let variantImage = GetYandexVariantInfo(oskuId, response)
                        variantImageArr.push(variantImage);

                        //let productCards = response.Data.results[0].data.collections.productCardJumpTableValues;
                        //let imgProductCards = Object.values(productCards).filter(item => item.type == "image").filter(item => item.transition.params.skuId != oskuId);
                        //let otherSkuIds = imgProductCards.map(item => item.transition.params.skuId);
                        //otherSkuIds = otherSkuIds.filter(item => item != oskuId);

                        if (cardVariantArr.length > 1) {
                            //多变体

                            // 创建任务队列
                            const tasks = new Array(cardVariantArr.length).fill(0).map((_, i) => {
                                return function task() {
                                    return new Promise((resolve) => {
                                        try {
                                            let currentVariant = cardVariantArr[i];
                                            bodyObj.params.forEach(item => {
                                                item.oskuId = currentVariant.oskuid;
                                            });

                                            if (currentVariant.pagehref)
                                                bodyObj.path = currentVariant.pagehref;

                                            funCallback({ Type: "GetAjaxResult", RequestMethod: "POST", RequestHeaders: headerObj, RequestUrl: queryRrl, RequestDataType: "json", RequestData: JSON.stringify(bodyObj) }, tab, function (otherResponse) {
                                                if (otherResponse.IsSuccess && otherResponse?.Data?.results[0]) {
                                                    const variantImage = GetYandexVariantInfo(currentVariant.skuid ? currentVariant.skuid : currentVariant.oskuid, otherResponse);
                                                    variantImageArr.push(variantImage);
                                                }
                                                else { }
                                                resolve(); // 确保任务结束后调用 resolve                                           
                                            }
                                            );
                                        } catch (e) {
                                            console.error("任务执行失败:", e);
                                            resolve(); // 即使报错也调用 resolve 防止卡住队列
                                        }
                                    });
                                };
                            });

                            //并发数
                            let taskOccurCount = cardVariantArr.length > 1 ? 2 : 1;

                            let btArr = null;
                            if (mainVariantDataType == 1) {
                                btArr = buildYandexVariants(mainVariantKeyCard.rows, oskuId);
                                btArr.forEach(item => {
                                    item.Property = JSON.stringify(item.Property);
                                });
                                propertyNames = mainVariantKeyCard.rows.map(x => x.id);
                            }

                            let finalVariants = [];
                            // 调用控制器 一次并发1-2个 并发数需要小于任务数，否则会报错
                            const Control = new ConcurrencyControl(tasks, taskOccurCount, function () {
                                //汇集产品图片
                                variantImageArr.forEach(x => {
                                    x.images.forEach(img => {
                                        if (imageList.indexOf(img) < 0)
                                            imageList.push(img);
                                    })
                                });

                                console.log("variantImageArr", JSON.stringify(variantImageArr));

                                if (mainVariantDataType == 1)
                                    finalVariants = attachYandexSkuInfo(btArr, variantImageArr);
                                else if (mainVariantDataType == 2) {
                                    for (const item of mainVariantKeyCard.snippets) {
                                        let skuName = item.productPayload.trainTitle.title.join('-');
                                        let itemBaseUrl = item.productPayload.gallery.mediaItems[0].picture.baseUrl;
                                        let currentVariant = {
                                            //skuId: skuName,
                                            VariantImageUrl: item.productPayload.gallery.mediaItems.map(item => {
                                                const url = item.picture.baseUrl;
                                                return url.endsWith("orig") ? url : url + "orig";
                                            }).join("|"),
                                            Property: JSON.stringify([{
                                                Key: mainVariantKeyCard.showAllTitle,
                                                Value: skuName
                                            }]),
                                        }

                                        const skuId = item.productPayload.offerParams?.oskuId || item.productPayload.targetLinkParams?.offerLinkParams?.oskuId;
                                        const foundVariantImage = variantImageArr.find(x =>
                                            String(x.skuId) === String(skuId)
                                        );
                                        if (foundVariantImage) {
                                            currentVariant.VariantImageUrl = foundVariantImage.images.join("|");
                                            currentVariant.Price = foundVariantImage.price
                                        }

                                        finalVariants.push(currentVariant);
                                    }
                                    propertyNames = [mainVariantKeyCard.showAllTitle];
                                }

                                var detailedDescription = mainVariantCardMeta?.description ? btoa(encodeURI(mainVariantCardMeta.description)) : "";
                                var briefDescription = mainVariantCardMeta?.description ? convertHtmlToPlainText(mainVariantCardMeta.description) : ""
                                Parameters = Array.from(
                                    new Map(Parameters.map(item => [item.Key, item])).values()
                                );
                                var box =
                                {
                                    "Title": mainVariantTitle.raw,
                                    "DetailedDescription": detailedDescription,
                                    "BriefDescription": briefDescription,
                                    "ImageUrl": imageList.join("|"),
                                    "PropertyName": propertyNames.length > 0 ? JSON.stringify(propertyNames) : "[]",
                                    "PlatformCategoryId": categoryId,
                                    "SourceUrl": souceUrl,
                                    "VideoUrl": '',
                                    "IsClaimed": false,
                                    "SourcePlatform": 42,
                                    "Tags": [],
                                    "Remark": "",
                                    "CreateTime": "1900-01-01 00:00:00",
                                    "Parameters": JSON.stringify(Parameters),
                                    "PlatformCategoryName": mainVariantCardMeta?.category ?? ""
                                };

                                if (fullDesc != "")
                                    box.DetailedDescription = fullDesc;

                                if (shortDesc != "")
                                    box.BriefDescription = convertHtmlToPlainText(shortDesc);

                                SaveProduct(tab, { "Box": box, "BoxItem": finalVariants }, funCallback);
                            });

                            Control.runTask(); // 执行队列任务
                        } else {
                            //单变体
                            mainVariantPara = Array.from(
                                new Map(mainVariantPara.map(item => [item.Key, item])).values()
                            );
                            let variant = {
                                "Price": mainVariantPrice?.mainPrice?.price?.value ?? 0,
                                "VariantImageUrl": variantImage.images.join("|"),
                                "Property": JSON.stringify(mainVariantPara)
                            };

                            try {
                                let imgArr = variantImage.images;
                                let firstImg = mainVariant.data.collections.complainForm[mainVariantKey].image;
                                if (firstImg)
                                    imgArr.unshift(firstImg);
                                let uniqueImgArr = [...new Set(imgArr)];
                                variant.VariantImageUrl = uniqueImgArr.join("|");
                            } catch (e) { }

                            variantArr.push(variant);

                            var detailedDescription = mainVariantCardMeta?.description ? btoa(encodeURI(mainVariantCardMeta.description)) : "";
                            var briefDescription = mainVariantCardMeta?.description ? convertHtmlToPlainText(mainVariantCardMeta.description) : "";
                            Parameters = Array.from(
                                new Map(Parameters.map(item => [item.Key, item])).values()
                            );
                            var box =
                            {
                                "Title": mainVariantTitle.raw,
                                "DetailedDescription": detailedDescription,
                                "BriefDescription": briefDescription,
                                "ImageUrl": variantImage.images.join("|"),
                                "PropertyName": "[]",
                                "PlatformCategoryId": categoryId,
                                "SourceUrl": souceUrl,
                                "VideoUrl": '',
                                "IsClaimed": false,
                                "SourcePlatform": 42,
                                "Tags": [],
                                "Remark": "",
                                "CreateTime": "1900-01-01 00:00:00",
                                "Parameters": JSON.stringify(Parameters),
                                "PlatformCategoryName": mainVariantCardMeta?.category ?? ""
                            };
                            if (fullDesc != "")
                                box.DetailedDescription = fullDesc;

                            if (shortDesc != "")
                                box.BriefDescription = convertHtmlToPlainText(shortDesc);

                            SaveProduct(tab, { "Box": box, "BoxItem": variantArr }, funCallback);
                        }

                    } else {
                        CategroyErrorCall("采集失败！若此错误频繁出现，请联系客服！", tab, funCallback);
                    }
                });

            });

        });
    }

    try {
        // https://market.yandex.ru/card 开头的链接需要请求页面拿到带参数的路径
        if (souceUrl.indexOf("market.yandex.ru/card") || souceUrl.indexOf("oskuId") == -1 || souceUrl.indexOf("businessId") == -1) {

            request(souceUrl, {
                responseType: "text",
                method: "GET"
            }).then(html => {
                console.log('YandexPageHtml', html);

                if ((html.indexOf("/checkcaptcha?") > 0 || html.indexOf("отключено исполнение JavaScript") > 0)) {
                    // 正则表达式匹配 action 属性值
                    const actionMatch = html.match(/action="([^"]+)"/);
                    if (actionMatch) {
                        const actionValue = actionMatch[1];
                        const verifyUrl = 'https://market.yandex.ru/' + actionValue;

                        funCallback({ "Type": "ShowYandexVerifyBox", "BoxHtml": '<iframe src="' + actionValue + '"' + ' style="width: 100%; height: 300px;" scrolling="auto" frameborder="0"></iframe>' }, tab, function (response) { });
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集被拦截！请完成验证！" }, tab, function (response) { });
                    } else {
                        funCallback({ "Type": "GetYandexProductInfo", "HtmlStr": html }, tab, function (response) {
                            if (response.data && response.data == {}) {
                                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "未获取到businessId" }, tab, function (response) { });
                                return;
                            }
                            AnalyzeYandexInfo(response.data.CardProductId, response.data.CardOskuId, response.data.CardBusinessId, response.variantArr);
                        });
                    }
                }
                else {
                    funCallback({ "Type": "GetYandexProductInfo", "HtmlStr": html }, tab, function (response) {
                        if (response.data && response.data == {}) {
                            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "未获取到businessId" }, tab, function (response) { });
                            return;
                        }
                        AnalyzeYandexInfo(response.data.CardProductId, response.data.CardOskuId, response.data.CardBusinessId, response.variantArr);
                    });
                }
            }).catch(reason => {
                catchFuncallback(reason, funCallback)
            });

        } else {
            AnalyzeYandexInfo("", "", "");
        }
    } catch (e) {
        CategroyErrorCall("采集失败！若此错误频繁出现，请联系客服！", tab, funCallback);
    }
}

//Yandex笛卡尔积
function DescartesByYandex(arr) {
    // 用于保存所有组合的数组
    let result = [];

    // 递归函数：生成组合
    function recurse(index, currentCombination) {
        // 如果已经遍历完所有对象，保存当前组合
        if (index === arr.length) {
            result.push(currentCombination.join('-'));
            return;
        }

        // 获取当前对象的visibleValues数组
        let visibleValues = arr[index].visibleValues;

        // 遍历visibleValues，递归生成组合
        for (let value of visibleValues) {
            recurse(index + 1, [...currentCombination, value]);
        }
    }

    // 从索引0开始递归
    recurse(0, []);

    return result;
}

//Yandex提取接口数据中的图片
function GetYandexVariantInfo(skuId, response) {
    const data = response.Data.results[0].data;
    const mediaItemMap = data.collections.mediaItem || {};
    const galleryMap = data.collections.gallery || {};

    let price = 0;
    try {
        price = data.collections.price[data.result].mainPrice.price.value;
    } catch (e) { }

    let variantImages = [];

    // 当前返回结果中的 gallery
    const gallery = Object.values(galleryMap)[0];

    if (gallery?.mediaItems) {
        gallery.mediaItems.forEach(mediaId => {
            const media = mediaItemMap[mediaId];

            if (media?.origUrl && /(9hq|orig)$/i.test(media.origUrl)) {
                variantImages.push(media.origUrl);
            }
        });
    }

    return {
        skuId,
        images: [...new Set(variantImages)],
        price
    };
}

function AnalyticalJF91Products(content, tab, souceUrl, funCallback) {
    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    request(souceUrl, { responseType: "text", method: "GET" }).then((res) => {
        let htmlStr = res;
        funCallback({ "Type": "GetJF91ProductInfo", "HtmlStr": htmlStr }, tab, function (response) {
            //请求sku的价格，图片
            if (response.IsSuccess) {
                response.Data.pageResponse = htmlStr;
                getMoreData(response.Data);
            } else {
                let model = {
                    Html: btoa(encodeURI(htmlStr)),
                    SourcePlatform: 43,
                    SouceUrl: souceUrl,
                    MoreData: JSON.stringify([]),
                };
                SaveLiknProduct(tab, model, funCallback);
            }
        });
    });

    //获取额外的变体数据并传递给后端
    function getMoreData(baseData) {
        let goodIds = baseData.dataIds;
        let variantData = [];
        let dataUrl = "https://detail.91jf.com/goods/spec/imgs";

        if (goodIds && goodIds.length > 0) {
            try {
                // 创建任务队列
                const tasks = new Array(goodIds.length).fill(0).map((_, i) => {
                    return function task() {
                        return new Promise((resolve) => {
                            try {
                                let dataId = goodIds[i];
                                let requestData = {
                                    spec_key_id: baseData.specs[0].spec[0].sp_id,
                                    spec_value_id: dataId,
                                    goods_id: baseData.goodsId.toString(),
                                };

                                funCallback({ Type: "GetAjaxResult", RequestMethod: "POST", RequestHeaders: {}, RequestUrl: dataUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: requestData, }, tab,
                                    function (response) {
                                        if (response.IsSuccess && response.Data.code == 10000) {
                                            let variantObj = {
                                                spValueId: dataId,
                                                variantInfo: response.Data.data,
                                            };
                                            variantData.push(variantObj);
                                        }
                                        resolve(); // 确保任务结束后调用 resolve
                                    }
                                );
                            } catch (e) {
                                console.error("任务执行失败:", e);
                                resolve(); // 即使报错也调用 resolve 防止卡住队列
                            }
                        });
                    };
                });
                // 调用控制器 一次并发两个
                const Control = new ConcurrencyControl(tasks, 2, function () {
                    let model = {
                        Html: btoa(encodeURI(baseData.pageResponse)),
                        SourcePlatform: 43,
                        SouceUrl: souceUrl,
                        MoreData: JSON.stringify(variantData),
                    };
                    SaveLiknProduct(tab, model, funCallback);
                });
                Control.runTask(); // 执行队列任务
            } catch (e) {
                let model = {
                    Html: btoa(encodeURI(baseData.pageResponse)),
                    SourcePlatform: 43,
                    SouceUrl: souceUrl,
                    MoreData: JSON.stringify(variantData),
                };
                SaveLiknProduct(tab, model, funCallback);
            }
        } else {
            let model = {
                Html: btoa(encodeURI(baseData.pageResponse)),
                SourcePlatform: 43,
                SouceUrl: souceUrl,
                MoreData: JSON.stringify(variantData),
            };
            SaveLiknProduct(tab, model, funCallback);
        }
    }
}

function AnalyticalAmazonProducts(content, tab, souceUrl, funCallback) {
    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    funCallback({ "Type": "GetAmazonVariantData", "SouceUrl": souceUrl }, tab, function (res) {
        let vData = [];
        if (res.variantData) {
            vData = res.variantData;
        }

        request(souceUrl, {
            responseType: "text"
            , method: "GET"
        }).then(data => {
            typeof (data) == "object" && (data = JSON.stringify(data));
            let model = {
                Html: btoa(encodeURI(data)),
                SourcePlatform: 4,
                SouceUrl: souceUrl,
                MoreData: JSON.stringify(vData)
            };
            SaveLiknProduct(tab, model, funCallback);
        }).catch(reason => {
            catchFuncallback(reason, funCallback)
        });
    });
}

function AnalyticalAlibabaProducts(content, tab, souceUrl, funCallback) {
    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    let url = souceUrl;
    var model = {
        Html: btoa(encodeURI(url)),
        SourcePlatform: 5,
        SouceUrl: souceUrl
    }; 

    if (url.indexOf('dj.1688.com') !== -1 || url.indexOf('detail.m.1688.com') !== -1) {
        request(url, {
            method: "GET",
            responseType: "text"
        }).then(detailResult => {
            if (detailResult && detailResult.indexOf('b2c_auction=') > -1) {
                var offerId = detailResult.split('b2c_auction=')[1].split('&')[0];
                url = 'https://detail.1688.com/offer/' + offerId + '.html';
                model.Html = btoa(encodeURI(url));
                model.SouceUrl = url;
            }
            SaveLiknProduct(tab, model, funCallback);
        }).catch(reason => {
            SaveLiknProduct(tab, model, funCallback);
        });

    } else {
        SaveLiknProduct(tab, model, funCallback);
    }
}

function AnalyticalAlibabaInternationProducts(content, tab, souceUrl, funCallback) {
    function extractProductId(url) {
        const regex = /product-detail\/[^_]+_([0-9]+)\.html/;
        const match = url.match(regex);
        return match ? match[1] : null;
    }

    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    request(souceUrl, {
        responseType: "text"
        , method: "GET"
    }).then(data => {
        typeof (data) == "object" && (data = JSON.stringify(data));

        let detailInfoId = extractProductId(souceUrl);
        if (detailInfoId != null && detailInfoId != 0) {

            let detailInfoUrl = "https://www.alibaba.com/event/app/mainAction/desc.htm?detailId=" + detailInfoId + "&language=en";
            fetch(detailInfoUrl, {
                method: 'GET', // 指定请求方法为 GET
                mode: 'cors'   // 允许跨域请求
            })
                .then(response => {
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    return response.text();
                })
                .then(detailData => {
                    let model = {
                        MoreData: detailData,
                        Html: btoa(encodeURI(data)),
                        SourcePlatform: 6,
                        SouceUrl: souceUrl
                    };
                    SaveLiknProduct(tab, model, funCallback);
                })
                .catch(error => {
                    let model = {
                        Html: btoa(encodeURI(data)),
                        SourcePlatform: 6,
                        SouceUrl: souceUrl
                    };
                    SaveLiknProduct(tab, model, funCallback);
                });
        }
        else {
            let model = {
                Html: btoa(encodeURI(data)),
                SourcePlatform: 6,
                SouceUrl: souceUrl
            };
            SaveLiknProduct(tab, model, funCallback);
        }

    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
}

function AnalyticalOldJoomProducts(content, tab, souceUrl, funCallback) {
    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    var pid = souceUrl.split("/");
    var tags = [];
    var images = [];
    var skus = [];
    var propertyName = [];

    if (!(content.data.header.mainImage == null || content.data.header.mainImage.images == null)) {
        var index = content.data.header.mainImage.images.length - 1;
        images.push(content.data.header.mainImage.images[index].url.split('?')[0]);//主图
    }

    if (content.data.header.hasOwnProperty("gallery") && content.data.header["gallery"] != null) {
        content.data.header.gallery.forEach(function (key) {
            var imgs = key.payload.images;
            images.push(imgs[imgs.length - 1].url);
        });
    }
    content.data.header.variants.forEach(function (item) {
        var property = [];
        var options = ["colors", "size"];
        var skuImage = (item.mainImage == null || item.mainImage.images == null || item.mainImage.images.length <= 0) ? "" : item.mainImage.images[item.mainImage.images.length - 1].url;

        if (item.hasOwnProperty("colors") && item.colors != null && item.colors.length > 0) {
            property.push({ Key: "colors", "Value": item["colors"][0].name });
            if (propertyName.indexOf("colors") === -1)
                propertyName.push("colors");
        }
        if (item.hasOwnProperty("size") && item.size != null && item.size !== "") {
            property.push({ Key: "size", "Value": item["size"] });
            if (propertyName.indexOf("size") === -1)
                propertyName.push("size");
        }

        var sku = {
            "Property": (null === property || 0 >= property.length) ? "[]" : JSON.stringify(property),
            "Price": (item.price == null || item.price.amount == null) ? 0.0 : item.price.amount,
            "Freight": (item.shippingOptions == null || item.shippingOptions.length <= 0 || item.shippingOptions[0].price == null || item.shippingOptions[0].price.price == null || item.shippingOptions[0].price.price.amount == null) ? 0.0 : item.shippingOptions[0].price.price.amount,
            "Currency": (item.price == null || item.price.currency == null) ? "USD" : item.price.currency,
            "VariantImageUrl": skuImage,
            "ShippingWeight": 0
        }
        skus.push(sku);
    });

    var box =
    {
        "Title": content.data.header.name,
        "BriefDescription": convertHtmlToPlainText(content.data.header.description),
        "DetailedDescription": btoa(encodeURI(content.data.header.description)),
        "ImageUrl": images.join('|'),
        "PropertyName": 0 >= propertyName.length ? "[]" : JSON.stringify(propertyName),
        "PlatformCategoryId": content.data.header.categoryId,
        "SourceUrl": souceUrl,
        "VideoUrl": "",
        "IsClaimed": false,
        "SourcePlatform": 7,
        "Tags": tags.join('|'),
        "Remark": "",
        "CreateTime": "1900-01-01 00:00:00",
        "Parameters": "[]"
    };
    SaveProduct(tab, { "Box": box, "BoxItem": skus }, funCallback);
}

function AnalyticalJoomProducts(content, tab, souceUrl, funCallback) {

    if (!content || content == "none" || !content.pageData)
        throw new Error("获取产品信息失败！");

    SaveProduct(tab, { "Box": content.pageData.box, "BoxItem": content.pageData.variantArr }, funCallback);

    //以下代码为2026-04-20前可以调用接口时的版本
    // if (content === "none")
    //     throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    // //如果拿不到请求头则走页面元素采集
    // if (content.info) {
    //     const { joomProId, lang } = extractJoomParams(souceUrl);
    //     funCallback({
    //         Type: "GetAjaxResult",
    //         RequestMethod: "POST",
    //         RequestHeaders: { "x-version": content.info["x-version"], "Authorization": content.info.Authorization },
    //         RequestUrl: `https://www.joom.com/api/1.1/products/${joomProId}/contentList/get?language=${lang}&_=lt44wprk`,
    //         RequestContentType: "application/json",
    //         RequestDataType: "json",
    //         RequestData: JSON.stringify({ appearance: {} }),
    //         Async: false,
    //     }, tab, function (response) {
    //         var model = {
    //             Html: JSON.stringify(response.Data.payload),
    //             SourcePlatform: 7,
    //             SouceUrl: souceUrl
    //         };
    //         SaveLiknProduct(tab, model, funCallback);
    //     })
    // } else {
    //     //旧版采集
    //     request(souceUrl,
    //         {
    //             responseType: "text"
    //             , method: "GET"
    //         }).then(data => {
    //             if (data.indexOf('__GL__loader') == -1) {
    //                 typeof (data) == "object" && (data = JSON.stringify(data));
    //                 var model = {
    //                     Html: btoa(encodeURI(data)),
    //                     SourcePlatform: 7,
    //                     SouceUrl: souceUrl
    //                 };
    //                 SaveLiknProduct(tab, model, funCallback);
    //             } else {
    //                 throw new Error("批量采集失败，请到商品详情页采集！");
    //             }
    //         }).catch(reason => {
    //             catchFuncallback(reason, funCallback)
    //         });
    // }
}

function extractJoomParams(url) {
    try {
        const urlObj = new URL(url);
        const pathname = urlObj.pathname; // "/en/products/670a47103ca9fe0107fb1ee7"

        // 提取语言（第一个路径段）
        const langMatch = pathname.match(/^\/([a-z]{2})\//);
        const lang = langMatch ? langMatch[1] : 'en'; // 默认 'en'

        // 提取商品 ID（24位十六进制字符串）
        const idMatch = pathname.match(/\/products\/([a-f0-9]{24})/i);
        const joomProId = idMatch ? idMatch[1] : null;

        return {
            joomProId,
            lang
        };
    } catch (e) {
        console.error("Invalid URL:", e);
        return { joomProId: null, lang: 'en' };
    }
}

function AnalyticalTaoBaoProducts(content, tab, souceUrl, funCallback) {
    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    //不准确，先注释：https://item.taobao.com/item.htm?ft=t&id=742496851808&priceTId=2147828617158331665637638ed398&pvid=096101c6-3c32-492c-8b16-3b7d91971618&qq-pf-to=pcqq.group&scm=1007.10302.274556.37515843_0_0&skuId=5317226883766&spm=a2113w.29182135.1788270250.16.7076bade8Lfy5f&utparam=%7B%22x_object_type%22:%22item%22,%22ald_res%22:%2234024916%22,%22tpp_buckets%22:%22302
    //if (souceUrl.indexOf("utparam=%7B") > -1) {
    //    AnalyticalTmallProducts(content, tab, souceUrl, '', funCallback);
    //    return;
    //}
    var sendMsgFun = funCallback;
    if (typeof receiveMessages === "function") {
        sendMsgFun = receiveMessages;
    }

    function ExcuteTaobaoProductData(tk) {
        if (tk.indexOf('_') > -1)
            tk = tk.split('_')[0];
        var time = new Date().getTime();

        var urlValueArr = souceUrl.split('?')[1],
            abbucket = '',
            id = '',//产品id
            pvid = '',
            ns = '',
            rn = '',
            spm = '',
            scm = '';

        if (urlValueArr.length) {
            urlValueArr = urlValueArr.split('&');
        }
        if (urlValueArr.length) {
            for (var i = 0; i < urlValueArr.length; i++) {
                var urlStr = urlValueArr[i];

                if (urlStr.indexOf('rn=') !== -1) {
                    rn = urlStr.split('rn=')[1];
                }
                if (urlStr.indexOf('ns=') !== -1) {
                    rn = urlStr.split('ns=')[1];
                }
                if (urlStr.indexOf('abbucket=') !== -1) {
                    abbucket = urlStr.split('abbucket=')[1];
                }
                if (urlStr.indexOf('id=') === 0) {
                    id = urlStr.split('id=')[1];
                }
                // if (urlStr.indexOf('pvid=') === 0) {
                //     pvid = urlStr.split('pvid=')[1];
                // }
                if (urlStr.indexOf('spm=') !== -1) {
                    spm = urlStr.split('spm=')[1];
                }
                if (urlStr.indexOf('scm=') !== -1) {
                    scm = urlStr.split('scm=')[1];
                }
            }
        }
        var detailData = JSON.stringify({
            "abbucket": abbucket, //获取url上的abbucket
            "id": id, //获取url上的id
            // "pvid": pvid, //获取url上的pvid，没有则取节点的值
            // "rn": rn, //获取url上的rn，可以为空
            "ns": ns, //获取url上的ns，可以为空
            "spm": spm, //获取url上的spm
            // "scm": scm, //获取url上的scm
            "detail_v": "3.3.0", //写死
            "preferWireless": "true" //写死，加上这个字段才能获取天猫新版页面的描述，新版页面的描述和旧版页面的描述不一样了，不加这个字段的话只能获取旧版页面的描述
        });
        var htmlData = JSON.stringify({
            "id": id,//获取url上的id，没有则取节点的值
            // "pvid": pvid, //获取url上的pvid，没有则取节点的值
            "detail_v": "3.3.2", //写死
            "exParams": JSON.stringify({
                "abbucket": abbucket, //获取url上的abbucket
                "id": id, //获取url上的abbucket
                // "pvid": pvid, //获取url上的pvid，没有则取节点的值
                "ns": rn, //获取url上的rn，可以为空
                "spm": spm, //获取url上的spm
                // "scm": scm, //获取url上的scm
                "queryParams": 'abbucket=' + abbucket + '&id=' + id + '&ns=' + ns + '&spm=' + spm + '&scm=' + scm,
                "domain": 'https://item.taobao.com',
                "path_name": '/item.htm'
            })
        });
        var dataSign = getTmallDataSign(tk, time, htmlData);
        var detailSign = getTmallSign(tk, time, detailData);
        var dataUrl = 'https://h5api.m.taobao.' + (souceUrl.indexOf('/detail.taobao.com/hk/item.htm?') !== -1 ? 'hk' : 'com') + '/h5/mtop.taobao.pcdetail.data.get/1.0/?jsv=2.6.1' +
            '&appKey=12574478&t=' + time + '&sign=' + dataSign + '&api=mtop.taobao.pcdetail.data.get' +
            '&v=1.0&ttid=2022%40taobao_litepc_9.17.0&isSec=0&ecode=0' + '&timeout=10000' +
            '&preventFallback=true' +
            '&AntiFlood=true&AntiCreep=true&H5Request=true&type=json&dataType=json' +
            '&data=' + escape(htmlData);
        var detailUrl = 'https://h5api.m.taobao.com/h5/mtop.taobao.detail.getdesc/7.0/?jsv=2.7.0' +
            '&appKey=12574478&t=' + time + '&sign=' + detailSign + '&api=mtop.taobao.detail.getdesc' +
            '&v=7.0&isSec=0&ecode=0&AntiFlood=true&AntiCreep=true&H5Request=true' +
            '&ttid=2022%40tmall_litepc_9.17.0&type=json&dataType=json' +
            '&data=' + escape(detailData);

        //批量采集失败，因为请求头中需要携带 "origin": "https://item.taobao.com", "referer": "https://item.taobao.com/" 这两个数据，但是给Ajax请求头设置这两个参数会被浏览器忽略
        sendMsgFun({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: dataUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
            if (response.IsSuccess) {
                var data = response.Data;
                if (data === null || data.data === null || data.data === {} || data.data.item === undefined || data.data.item === null) {
                    //有验证码需滑动验证码
                    if (data &&
                        data.data &&
                        data.data.url &&
                        data.data.url !== null) {
                        sendMsgFun({ "Type": "ShowTmallVerifyBox", "BoxHtml": '<iframe src="' + data.data.url + '"' + ' style="width: 100%; height: 300px;" scrolling="auto" frameborder="0"></iframe>' }, tab, function (response) { });
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集被拦截！请滑动验证码！" }, tab, function (response) { });
                    } else {
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集数据为空，请稍后重试！" }, tab, function (response) { });
                    }

                    sendMsgFun({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
                    return;
                }

                var model = {
                    Html: btoa(encodeURI(JSON.stringify(data.data))),
                    SourcePlatform: 11,
                    SouceUrl: souceUrl
                };


                funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: detailUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab,
                    function (response) {
                        if (response.IsSuccess) {
                            let detailResult = response.Data;
                            if (detailResult &&
                                detailResult.data &&
                                detailResult.data.components &&
                                detailResult.data.components.componentData) {
                                if (detailResult.data.components.componentData.desc_richtext_pc &&
                                    detailResult.data.components.componentData.desc_richtext_pc.model &&
                                    detailResult.data.components.componentData.desc_richtext_pc.model.text) {
                                    data.data.DetailedDescription = detailResult.data.components.componentData.desc_richtext_pc.model.text;
                                    model.Html = btoa(encodeURI(JSON.stringify(data.data)));
                                } else if (detailResult.data.components.layout &&
                                    detailResult.data.components.layout.length > 0) {//第二种方式，手动拼接html5
                                    var detailHtmlArr = [];
                                    for (var i = 0; i < detailResult.data.components.layout.length; i++) {
                                        var currentKey = detailResult.data.components.layout[i].ID;
                                        if (detailResult.data.components.componentData.hasOwnProperty(currentKey) &&
                                            detailResult.data.components.componentData[currentKey] != null &&
                                            detailResult.data.components.componentData[currentKey].model != null) {
                                            var rowData = detailResult.data.components.componentData[currentKey];
                                            var rowHtml = "";
                                            var style = "";
                                            if (rowData.styles && rowData.styles.size) {
                                                style += "width:" + rowData.styles.size.width + "px;";
                                                style += "height:" + rowData.styles.size.height + "px;";
                                            }
                                            if (rowData.model.picUrl && rowData.model.picUrl.length > 0) {
                                                rowHtml += '<p><img style="' + style + '" src="' + rowData.model.picUrl + '" /></p>';
                                            }
                                            if (rowData.model.text && rowData.model.text.length > 0) {
                                                rowHtml += '<p>' + rowData.model.text + '</p>';
                                            }
                                            if (rowHtml.length > 0) {
                                                rowHtml = '<div>' + rowHtml + '</div>';
                                                detailHtmlArr.push(rowHtml);
                                            }
                                        }
                                    }

                                    if (detailHtmlArr.length > 0) {
                                        data.data.DetailedDescription = "<div>" + detailHtmlArr.join("") + "</div>";
                                        model.Html = btoa(encodeURI(JSON.stringify(data.data)));
                                    }
                                }

                            }
                            SaveLiknProduct(tab, model, funCallback);
                        } else {
                            SaveLiknProduct(tab, model, funCallback);
                        }
                    }
                );


                //请求完SKU信息，再继续请求图文描述，图文描述如果请求失败，可以忽略
                // try {
                //     //这里有跨域报错，不能拿到前台做请求
                //     request(detailUrl, {
                //         method: "GET",
                //         responseType: "json"
                //     }).then(detailResult => {
                //         if (detailResult &&
                //             detailResult.data &&
                //             detailResult.data.components &&
                //             detailResult.data.components.componentData) {
                //             if (detailResult.data.components.componentData.desc_richtext_pc &&
                //                 detailResult.data.components.componentData.desc_richtext_pc.model &&
                //                 detailResult.data.components.componentData.desc_richtext_pc.model.text) {
                //                 data.data.DetailedDescription = detailResult.data.components.componentData.desc_richtext_pc.model.text;
                //                 model.Html = btoa(encodeURI(JSON.stringify(data.data)));
                //             } else if (detailResult.data.components.layout &&
                //                 detailResult.data.components.layout.length > 0) {//第二种方式，手动拼接html5
                //                 var detailHtmlArr = [];
                //                 for (var i = 0; i < detailResult.data.components.layout.length; i++) {
                //                     var currentKey = detailResult.data.components.layout[i].ID;
                //                     if (detailResult.data.components.componentData.hasOwnProperty(currentKey) &&
                //                         detailResult.data.components.componentData[currentKey] != null &&
                //                         detailResult.data.components.componentData[currentKey].model != null) {
                //                         var rowData = detailResult.data.components.componentData[currentKey];
                //                         var rowHtml = "";
                //                         var style = "";
                //                         if (rowData.styles && rowData.styles.size) {
                //                             style += "width:" + rowData.styles.size.width + "px;";
                //                             style += "height:" + rowData.styles.size.height + "px;";
                //                         }
                //                         if (rowData.model.picUrl && rowData.model.picUrl.length > 0) {
                //                             rowHtml += '<p><img style="' + style + '" src="' + rowData.model.picUrl + '" /></p>';
                //                         }
                //                         if (rowData.model.text && rowData.model.text.length > 0) {
                //                             rowHtml += '<p>' + rowData.model.text + '</p>';
                //                         }
                //                         if (rowHtml.length > 0) {
                //                             rowHtml = '<div>' + rowHtml + '</div>';
                //                             detailHtmlArr.push(rowHtml);
                //                         }
                //                     }
                //                 }

                //                 if (detailHtmlArr.length > 0) {
                //                     data.data.DetailedDescription = "<div>" + detailHtmlArr.join("") + "</div>";
                //                     model.Html = btoa(encodeURI(JSON.stringify(data.data)));
                //                 }
                //             }

                //         }
                //         SaveLiknProduct(tab, model, funCallback);
                //     }).catch(reason => {
                //         SaveLiknProduct(tab, model, funCallback);
                //     });
                // } catch (e) {
                //     SaveLiknProduct(tab, model, funCallback);
                // }


            } else {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "淘宝采集被拦截！请刷新淘宝页面重试！" }, tab, function (response) { });
                sendMsgFun({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
        });
    }

    //本地缓存Token获取淘宝产品（适用于批量采集）
    function ExcuteTaobaoProductDataByLocalTk() {
        chrome.storage.local.get(['wyystaobaoh5tk'], function (result) {
            var tk = result.wyystaobaoh5tk;
            ExcuteTaobaoProductData(tk);
        });
    }

    sendMsgFun({ "Type": "GetDocumentCookies", "NeedNameArr": ["_m_h5_tk"] }, tab, function (response) {
        if (response && response._m_h5_tk && response._m_h5_tk.length > 0) {
            ExcuteTaobaoProductData(response._m_h5_tk);
        } else {
            chrome.storage.local.get(['wyystaobaoh5tk'], function (result) {
                var tk = result.wyystaobaoh5tk;
                if (!tk) {//凭据不存在就调用下接口，会自动刷新凭证
                    request("https://h5api.m.taobao.com/h5/mtop.taobao.pcdetail.data.get/1.0/?jsv=2.6.1&appKey=12574478&t=1704881502814", {
                        method: "GET",
                        responseType: "json"
                    }).then(data => {
                        ExcuteTaobaoProductDataByLocalTk();
                    }).catch(reason => {
                        ExcuteTaobaoProductDataByLocalTk();
                    });
                } else {
                    ExcuteTaobaoProductDataByLocalTk();
                }
            });
        }
    });
}

// 获取拼多多产品cookie
function getPDDCookies(url, resolve) {
    chrome.cookies.getAll({
        url: url,
    }, function (cookies) {
        var token = cookies.find(item => item.name === 'PDDAccessToken');
        var userId = cookies.find(item => item.name === 'pdd_user_id');
        resolve({ 'accessToken': token ? token.value : '', 'userId': userId ? userId.value : '' });
    });
}

function getPddRequest(url, callback) {
    var origin = new URL(url).origin;
    getPDDCookies(origin + '/', cookie => {
        callback(origin, cookie)
    });
}
// getPddRequest(url, function(origin, cookie){
//     var params = {
//         "address_id": addressInfo.addressId,
//         "address_snapshot_id": addressInfo.addressSnapshotId,
//         "goods": [
//           {
//             "sku_id": Number(searchParams.sku_id),
//             "sku_number": Number(searchParams.goods_number),
//             "goods_id": searchParams.goods_id
//           }
//         ],
//         "source_channel": pddRawData.sourceChannel || '0',
//         "group_id": pddRawData.groupId,
//         "source_type": 0,
//         "attribute_fields": pddRawData.extendMap,
//         promotion_union_vo,
//         ...active
//     };
//     fetch(origin + '/proxy/api/' + orderServicePath + '?pdduid=' + cookie.userId, {
//         method: 'post',
//         headers: {
//             'Content-Type': 'application/json',
//             'accesstoken': cookie.accessToken,
//         },
//         body: JSON.stringify(params),
//     }).then(response => response.json()).then(function (res){
//         sendResponse({success: true, ...res});
//         chrome.windows.remove(tabId);
//     }).catch(res => {
//         sendResponse({success: false, ...res});
//         chrome.windows.remove(tabId);
//     });
// })


// 回调方法
var handlePddEv = {
    registry: {},

    on: function (k, v) {
        this.registry[k] = v;
    },
    trigger: function (k) {
        var args = [];
        for (var i = 1; i < arguments.length; i++) {
            args.push(arguments[i]);
        }
        return this.registry[k] && this.registry[k].apply(this.registry[k], args);
    }
};
// 拼多多信息
var pddInfo = {
    event: handlePddEv,
    addressInfo: {
        intval: 0,
    },
    expressInfo: {
        intval: 0,
    },
    couponInfo: {
        intval: 0
    },
    personal: {
        data: {}
    },
    orderList: {
        tabId: null,
        closeTab: function (tabId) {
            tabId && chrome.windows.remove(tabId);
        }
    }
}

var tabId = '';
function GetPddInfo(tab, url, funCallback, content, productTitle) {
    var TIMEOUT = 15e3;
    var tabId = tabId; // 你的tab ID
    //去除链接多余参数，保留goods_id
    function getUrlWithGoodsId(urlStr) {
        const [baseUrl, queryString] = urlStr.split('?');  // 分离 URL 和参数部分
        if (!queryString) return urlStr;
        const queryParams = queryString.split('&');
        const goodsIdParam = queryParams.find(param => param.startsWith('goods_id='));  // 找到包含 goods_id 的参数
        if (!goodsIdParam) return baseUrl;    // 如果没有找到 goods_id，返回基础 URL
        return `${baseUrl}?${goodsIdParam}`;  // 返回只包含 goods_id 的 URL
    }

    let newUrl = getUrlWithGoodsId(url);
    funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: url, RequestContentType: "text/html; charset=utf-8", RequestDataType: "html", RequestData: {} }, tab, function (response) {
        if (response.IsSuccess) {
            var responseText = response.Data;// 获取服务器返回的文本内容
            //console.log("responseText", responseText);
            if (productTitle != "" && responseText.indexOf(productTitle) < 0) {
                //当返回的数据中不包含标题，则说明没有数据返回，使用页面采集
                AnalyticalHtmlPinDuoDuoProducts(content.jsonData, tab, url, funCallback);
            } else {
                funCallback({ "Type": "CheckPinDuoDuoProductInfo", "HtmlStr": responseText, "SouceUrl": url }, tab, function (response) {
                    let pagePrice = 0;
                    try {
                        pagePrice = parseFloat(content.priceText)
                    } catch { }

                    let responseDataJson = JSON.stringify(response.data);
                    let isExistPageJson = responseDataJson.includes("goodsName");
                    let isExistSpecValue = responseDataJson.includes("spec_value");
                    content.priceText = content.priceText ? content.priceText : "";
                    if (isExistPageJson && isExistSpecValue && (pagePrice != 0 && !content.priceText.includes('?'))) {
                        //页面有json则使用页面json
                        var model = {
                            Html: btoa(encodeURI(JSON.stringify(response.data))),
                            SourcePlatform: 12,
                            SouceUrl: newUrl,
                            Price: pagePrice,
                        };
                        SaveLiknProduct(tab, model, funCallback);
                    } else {
                        funCallback({ "Type": "GetPinDuoDuoSkuInfo", "SouceUrl": url }, tab, function (skuInfoResponse) {
                            //若批量采集没有得到页面json则直接报错
                            if (skuInfoResponse.data == "批量采集失败") {
                                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "拼多多采集接口不稳定，推荐产品详情页内采集" }, tab, function (response) { });
                                return;
                            }

                            //接口返回有数据则使用接口数据
                            if (skuInfoResponse.data.sku && response.data.includes('viewImageData') && !response.data.includes('"viewImageData": []')) {

                                var model = {
                                    Html: btoa(encodeURI(JSON.stringify(response.data))),
                                    SourcePlatform: 12,
                                    SouceUrl: newUrl,
                                    Price: pagePrice,
                                    MoreData: JSON.stringify(skuInfoResponse.data)
                                };
                                SaveLiknProduct(tab, model, funCallback);
                            } else {
                                //页面没有json和接口不返回数据后使用页面DOM采集
                                funCallback({ "Type": "GetPinDuoDuoHtmlData", "SouceUrl": url }, tab, function (htmlResponse) {
                                    let htmlResponseJson = JSON.stringify(htmlResponse);
                                    var model = {
                                        Html: btoa(encodeURI(JSON.stringify(response.data))),
                                        SourcePlatform: 12,
                                        SouceUrl: newUrl,
                                        Price: pagePrice,
                                        MoreData: htmlResponseJson
                                    };
                                    SaveLiknProduct(tab, model, funCallback);
                                });
                            }
                        });
                    }
                });
            }
            return;
        } else {
            AnalyticalHtmlPinDuoDuoProducts(content.jsonData, tab, souceUrl, funCallback);
        }
    });
}

function AnalyticalPinDuoDuoProducts(content, tab, souceUrl, funCallback) {
    var productTitle = "";
    if (content?.store?.initDataObj?.goods?.goodsName)
        productTitle = content.store.initDataObj.goods.goodsName;

    //判断souceUrl 包含 mobile.yangkeduo.com 时执行
    if (souceUrl.indexOf("mobile.yangkeduo.com") > -1 || souceUrl.indexOf("mobile.pinduoduo.com") > -1) {
        chrome.windows.create({ "url": souceUrl, width: 1, height: 1, top: 1920, left: 0 }, function (tab) {
            tabId = tab.id;

            chrome.windows.update(tab.id, { focused: false, width: 1, height: 1, top: 1920 });
            var origin = new URL(souceUrl).origin;
            getPDDCookies(origin + '/', result => {
                if (!result.userId) {
                    clearTimeout(pddInfo.expressInfo.intval);
                    throw new Error('请先登录拼多多账号');
                    chrome.windows.remove(tab.id);
                }
            });
            chrome.windows.remove(tabId);
        });
        GetPddInfo(tab, souceUrl, funCallback, content, productTitle);
        return;
    }

    if (content === "none")
        throw new Error("获取sku信息失败！");
    //判断souceUrl中的域名是否为：pifa.pinduoduo.com 
    if (souceUrl.indexOf('pifa.pinduoduo.com') >= 0) {
        //将content 对象转换为json字符串
        var jsonContent = JSON.stringify(content);
        var model = {
            Html: btoa(encodeURI(jsonContent)),
            SourcePlatform: 12,
            SouceUrl: souceUrl
        };
        SaveLiknProduct(tab, model, funCallback);
        return;
    }

    AnalyticalHtmlPinDuoDuoProducts(content, tab, souceUrl, funCallback);
}

//拼多多页面解析
function AnalyticalHtmlPinDuoDuoProducts(content, tab, souceUrl, funCallback) {

    //描述
    var briefDescription = "";
    content.store.initDataObj.goods.goodsProperty.map((item, index) => {
        briefDescription += item.key + ':' + item.values.join("，");
        if (index < content.store.initDataObj.goods.goodsProperty.length - 1)
            briefDescription += "\n";
    });
    var detailedDescription = "";
    content.store.initDataObj.goods.goodsProperty.map((item, index) => {
        detailedDescription += "<li>" + item.key + ':' + item.values.join("，") + "</li>";
    });
    detailedDescription = "<ul>" + detailedDescription + "</ul>";
    //参数
    var parameters = content.store.initDataObj.goods.goodsProperty.map(x => {
        return {
            Key: x.key,
            Value: x.values.join("，"),
        }
    });
    //属性
    var propertyNames = [];
    if (content.store.initDataObj.goods.skus.length > 0)
        propertyNames = content.store.initDataObj.goods.skus[0].specs.map(x => x.spec_key);
    //视频地址
    var videoUrl = content.store.initDataObj.goods.videoGallery.map(x => x.url).join("|");
    //图片
    var imageUrls = content.store.initDataObj.goods.viewImageData;
    content.store.initDataObj.goods.detailGallery.map(x => {
        if (imageUrls.indexOf(x.url) < 0)
            imageUrls.push(x.url);
    });

    var skus = [];
    content.store.initDataObj.goods.skus.map(x => {
        var sku = {};
        var propertys = x.specs.map(y => {
            return {
                Key: y.spec_key,
                Value: y.spec_value,
            }
        });

        sku.Property = JSON.stringify(propertys);
        sku.Price = x.groupPrice;
        sku.Freight = 0;
        sku.Currency = "CNY";
        sku.VariantImageUrl = x.thumbUrl;
        sku.ShippingWeight = x.weight;
        skus.push(sku);
    });

    var productInfo = {};
    productInfo.Title = content.store.initDataObj.goods.goodsName;
    productInfo.BriefDescription = convertHtmlToPlainText(briefDescription);
    productInfo.DetailedDescription = detailedDescription;
    productInfo.ImageUrl = imageUrls.join('|');

    productInfo.PropertyName = JSON.stringify(propertyNames);
    productInfo.CategoryId = "";
    productInfo.SourceUrl = souceUrl;
    productInfo.VideoUrl = videoUrl;
    productInfo.IsClaimed = false;
    productInfo.SourcePlatform = 12;
    productInfo.Tags = "";
    productInfo.Remark = "";
    productInfo.CreateTime = "1900-01-01 00:00:00";
    productInfo.Parameters = JSON.stringify(parameters); //忽略 
    SaveProduct(tab, { "Box": productInfo, "BoxItem": skus }, funCallback);
}

function AnalyticalOnBuyProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服：" + souceUrl);

    var notificationKey = new Date().getTime();
    var imageList = [];
    content.propertyNames = [];
    content.SkuList = [];
    var getSpuInfo = function () {

    }
    var getvariationsInfo = function (sku, index) {
        return new Promise(resolve => {
            request(`https://www.onbuy.com/gb/frontend/product/get-attribute-data.html?product_id=${content.productId}&attribute_1=${sku.attribute1Id}&&changed=attribute_1&condition=1&attribute_2=${sku.attribute2Id}`, {
                responseType: "text"
                , method: "GET"
            }).then(res => {
                funCallback({ "Type": "GetOnbuyVariationsInfo", "HtmlStr": res.in_stock }, tab, function (response) {
                    let skuFirstImage = response.SkuFirstImage;
                    let price = response.Price;

                    var firstImage = '';
                    var hasImageSku;
                    if (sku.attributeKey1.toLowerCase() === 'color' || sku.attributeKey1.toLowerCase() === 'colour') {
                        hasImageSku = content.Skus.find(x => x.attribute1Id == sku.attribute1Id && x.imageUrl != firstImage);
                    }
                    if (sku.attributeKey2 && (sku.attributeKey2.toLowerCase() === 'color' || sku.attributeKey2.toLowerCase() === 'colour')) {
                        hasImageSku = content.Skus.find(x => x.attribute2Id == sku.attribute2Id && x.imageUrl != firstImage);
                    }

                    if (!imageList.includes(skuFirstImage) && !hasImageSku) {
                        imageList.push(skuFirstImage);
                    }
                    if (hasImageSku) {
                        skuFirstImage = hasImageSku.imageUrl;
                    }
                    content.Skus[index].price = price;
                    content.Skus[index].imageUrl = skuFirstImage;
                    resolve();
                });
            }).catch(reason => {
                console.log(reason);
                resolve();
            });
        });
    }

    //生成sku信息
    var setSku = function generateCombinations(properties) {
        const combinations = [];

        function helper(index, combination) {
            if (index === properties.length) {
                combinations.push(combination);
                return;
            }

            const property = properties[index];
            const values = property.value;

            for (const value of values) {
                const newCombination = { ...combination };
                newCombination[`attributeKey${index + 1}`] = property.key.replace(":", '');
                newCombination[`attributeValue${index + 1}`] = value.value;
                newCombination[`attribute${index + 1}Id`] = value.id;
                newCombination['price'] = content.price;
                newCombination['imageUrl'] = '';
                newCombination['hasStock'] = 0;
                helper(index + 1, newCombination);
            }
        }

        helper(0, {});

        return combinations;
    }

    var saveProductData = function () {
        var box =
        {
            "Title": content.title,
            "DetailedDescription": btoa(encodeURI(content.desc)),
            "BriefDescription": convertHtmlToPlainText(content.desc),
            "ImageUrl": imageList.join("|"),
            "PropertyName": content.propertyNames.length > 0 ? JSON.stringify(content.propertyNames) : "[]",
            "PlatformCategoryId": content.categoryId,
            "SourceUrl": souceUrl,
            "VideoUrl": '',
            "IsClaimed": false,
            "SourcePlatform": 27,
            "Tags": [],
            "Remark": "",
            "CreateTime": "1900-01-01 00:00:00",
            "Parameters": JSON.stringify(content.Parameters),
            "PlatformCategoryName": content.categoryName
        };
        funCallback({ "Type": "NotificationClose", "Key": notificationKey }, tab, () => { });
        SaveProduct(tab, { "Box": box, "BoxItem": content.SkuList }, funCallback);
    }
    async function startRequest() {
        funCallback({ "Type": "GetOnbuyPageHtml", "SouceUrl": souceUrl }, tab, function (pageResponse) {
            let data = pageResponse.data
            // typeof (data) == "object" && (data = JSON.stringify(data));
            funCallback({ "Type": "GetOnbuyProductInfo", "HtmlStr": data }, tab, function (response) {
                content.title = response.Title;
                content.desc = response.Desc;
                content.categoryName = response.CategoryName;
                content.categoryId = response.CategoryId;
                content.Parameters = response.Parameters;

                content.propertyNames = [];

                for (var i = 0; i < response.ImageList.length; i++) {
                    imageList.push(response.ImageList[i])
                }

                if (response.HasMoreSku) {
                    content.productId = response.ProductId;
                    content.propertyNames = response.PropertyNames;
                    content.Skus = response.Skus;

                    var tasks = []
                    for (i = 0; i < content.Skus.length; i++) {
                        //if (content.Skus[i].hasStock === 1) {
                        //如果有库存，就调接口获取信息，如果没有就跳过
                        tasks.push(getvariationsInfo(content.Skus[i], i));
                        //}

                    }
                    Promise.all(tasks).then(result => {
                        if (content.Skus) {
                            for (i = 0; i < content.Skus.length; i++) {
                                if (content.Skus[i].hasStock === 0) {
                                    if (content.Skus[i].attributeKey1 && (content.Skus[i].attributeKey1.toLowerCase() === 'color' || content.Skus[i].attributeKey1.toLowerCase() === 'colour')) {
                                        var stockVariation = content.Skus.find(x => x.hasStock === 1 && x.attributeValue1 == content.Skus[i].attributeValue1);
                                        if (stockVariation) {
                                            content.Skus[i].imageUrl = stockVariation.imageUrl;
                                        }
                                    }
                                    if (content.Skus[i].attributeKey2 && (content.Skus[i].attributeKey2.toLowerCase() === 'color' || content.Skus[i].attributeKey2.toLowerCase() === 'colour')) {
                                        var stockVariation = content.Skus.find(x => x.hasStock === 1 && x.attributeValue2 == content.Skus[i].attributeValue2);
                                        if (stockVariation) {
                                            content.Skus[i].imageUrl = stockVariation.imageUrl;
                                        }
                                    }

                                }
                                var property = [{ Key: content.Skus[i].attributeKey1, Value: content.Skus[i].attributeValue1 }];
                                if (content.Skus[i].attributeKey2) {
                                    property.push({ Key: content.Skus[i].attributeKey2, Value: content.Skus[i].attributeValue2 });
                                }
                                content.SkuList.push({
                                    Price: content.Skus[i].price,
                                    Property: JSON.stringify(property),
                                    Currency: content.currency,
                                    VariantImageUrl: content.Skus[i].imageUrl,
                                })
                            }
                        }
                        saveProductData();
                    }).catch(error => {
                        funCallback({ "Type": "NotificationClose", "Key": notificationKey }, tab, () => { });
                        //异步,无法触发到上层函数的TryCatch,自行提示
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "OnBuy产品解析失败！" + error.message }, tab, function (response) { });
                        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
                    });
                } else {
                    //单属性
                    let currentPrice = content.price;
                    if (!content.price)
                        currentPrice = response.Price;
                    content.SkuList = [{
                        Price: currentPrice,
                        Property: "[]",
                        Currency: content.currency,
                        VariantImageUrl: imageList.join('|'),
                    }]
                    saveProductData();
                }
            });
        });
    }
    startRequest();
}
function AnalyticalOzonProducts(content, tab, souceUrl, funCallback) {
    if (content == "none" || content == undefined)
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    if (content.Info == "刷新重试") {
        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "未能获取到完整数据，请刷新页面后重试，若此错误频繁出现，请联系客服！" }, tab, function (response) { });
        return;
    }

    var notificationKey = new Date().getTime();
    funCallback({ "Type": "NotificationShow", "MessageType": "info", "Message": "抓取产品中...", "Key": notificationKey }, tab, () => { });

    var isVariant = content.SkuLinks.length > 0;
    var requestIndex = 0;

    var allImages = [];
    if (content.Skus.some(x => x.VariantImageUrl && x.VariantImageUrl.length > 0)) {
        content.Skus[0].VariantImageUrl.forEach(x => {
            allImages.push(x);
        });
    }

    var briefDescription = "";
    var detailedDescription = "";
    var richJson = "";
    var descriptionCategoryId = '';

    //获取单变体数据
    var getSingleVariantData = function () {
        return new Promise(resolve => {
            let requestUrl = 'https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=' + content.Url;
            if (souceUrl.indexOf("ozon.by") > -1) {
                requestUrl = 'https://ozon.by/api/composer-api.bx/page/json/v2?url=' + content.Url;
            } else if (souceUrl.indexOf("ozon.kz") > -1) {
                requestUrl = 'https://ozon.kz/api/composer-api.bx/page/json/v2?url=' + content.Url;
            } else {
                let originUrl = new URL(souceUrl).origin;
                requestUrl = originUrl + '/api/composer-api.bx/page/json/v2?url=' + content.Url;
            }
            funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: requestUrl, RequestContentType: "application/json", RequestDataType: "json", RequestData: {}, Async: true, }, tab, function (response) {
                if (response.IsSuccess) {
                    let data = response.Data;
                    var webGalleryModel = null;
                    var webPrice = null;
                    for (var item in data.widgetStates) {
                        if (item.indexOf("webGallery-") > -1) {
                            webGalleryModel = JSON.parse(data.widgetStates[item]);
                        }
                        if (item.indexOf("webPrice-") > -1) {
                            webPrice = JSON.parse(data.widgetStates[item]);
                        }
                    }

                    if (webGalleryModel) {
                        //获取视频链接
                        if (webGalleryModel.videoCover && webGalleryModel.videoCover.url) {
                            content.VideoUrl = webGalleryModel.videoCover.url;
                        }

                        let currentPrice = "";
                        if (webPrice.hasOwnProperty('cardPrice')) {
                            currentPrice = webPrice.cardPrice;
                        } else {
                            currentPrice = webPrice.price;
                        }

                        var currency = GetcurrencyCode(currentPrice, "RUB");

                        content.Skus = [{
                            Property: "[]",
                            Price: currentPrice.replaceAll(",", ".").replace(/[^\d^.]/g, ""),
                            Currency: currency,
                            VariantImageUrl: webGalleryModel.images.map(y => y.src),
                        }];
                    }

                    resolve();
                } else {
                    //resolve();
                    reject(new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！"));
                }
            });
        });
    }

    //获取多变体图片
    var getVariantImageData = function (url) {
        return new Promise(resolve => {
            let requestUrl = 'https://www.ozon.ru/api/composer-api.bx/page/json/v2?url=' + url;
            if (souceUrl.indexOf("ozon.by") > -1) {
                requestUrl = 'https://ozon.by/api/composer-api.bx/page/json/v2?url=' + url;
            } else if (souceUrl.indexOf("ozon.kz") > -1) {
                requestUrl = 'https://ozon.kz/api/composer-api.bx/page/json/v2?url=' + url;
            } else {
                let originUrl = new URL(souceUrl).origin;
                requestUrl = originUrl + '/api/composer-api.bx/page/json/v2?url=' + url;
            }
            funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: requestUrl, RequestContentType: "application/json", RequestDataType: "json", RequestData: {}, Async: true, }, tab, function (response) {
                if (response.IsSuccess) {
                    let data = response.Data;
                    var webGalleryModel = null;
                    var aspectsModel = null;
                    for (var item in data.widgetStates) {
                        if (item.indexOf("webGallery-") > -1) {
                            webGalleryModel = JSON.parse(data.widgetStates[item]);
                        }
                        if (item.indexOf("webAspects-") > -1) {
                            aspectsModel = JSON.parse(data.widgetStates[item]);
                        }
                    }

                    if (!webGalleryModel) {
                        content.SkuLinks = content.SkuLinks.filter(x => x.Link != url);
                        resolve();
                        return;
                    }

                    //获取视频链接
                    if (webGalleryModel.videoCover && webGalleryModel.videoCover.url && !content.VideoUrl) {
                        content.VideoUrl = webGalleryModel.videoCover.url;
                    }

                    //图片赋值
                    content.SkuLinks.forEach(x => {
                        if (x.Link == url) {
                            x.ImageUrls = webGalleryModel.images.map(y => y.src);
                        }
                    });

                    //获取变体
                    //当前页面sku、sku链接
                    var selfSku = {};
                    if (aspectsModel) {
                        aspectsModel.aspects.forEach(x => {
                            var key = "";
                            if (x.descriptionRs && x.descriptionRs.length > 0) {
                                key = x.descriptionRs[0].content.replace(": ", "").replace(":", "");
                            }
                            x.variants.forEach(variant => {
                                if (variant.sku == webGalleryModel.sku) {
                                    var property = [];
                                    if (selfSku.Property) {
                                        property = JSON.parse(selfSku.Property);
                                    }
                                    if (key) {
                                        property.push({ Key: key, Value: variant.data.searchableText });
                                    }

                                    var currency = GetcurrencyCode(variant.data.price, "RUB");

                                    selfSku.Price = variant.data.price.replaceAll(",", ".").replace(/[^\d^.]/g, "");
                                    selfSku.SkuCode = variant.sku;
                                    selfSku.Property = JSON.stringify(property);
                                    selfSku.Currency = currency;
                                }

                                if (!content.SkuLinks.some(y => y.SkuCode == variant.sku)) {
                                    content.SkuLinks.push({
                                        SkuCode: variant.sku,
                                        Link: variant.link,
                                        ImageUrls: null,
                                    });
                                }
                            });
                        });
                        selfSku.VariantImageUrl = webGalleryModel.images.map(y => y.src);
                        if (!content.Skus.some(x => x.SkuCode == selfSku.SkuCode)) {
                            content.Skus.push(selfSku);
                        }
                    }
                    resolve();
                } else {
                    //resolve();
                    reject(new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！"));
                }
            });
        });
    }

    //获取公共参数和描述
    var getParameterData = function () {
        return new Promise(resolve => {
            let baseUrl = "https://www.ozon.ru/";
            if (souceUrl.indexOf("ozon.by") > -1) {
                baseUrl = "https://ozon.by/";
            } else if (souceUrl.indexOf("ozon.kz") > -1) {
                baseUrl = "https://ozon.kz/";
            } else {
                baseUrl = new URL(souceUrl).origin + "/";
            }

            var url = content.Url;
            if (url.indexOf("?") > -1) {
                url = baseUrl + "api/entrypoint-api.bx/page/json/v2?url=" + url.substring(0, url.indexOf("?")) + "/?layout_container=pdpPage2column&layout_page_index=2&oos_search=false&sh=Ip0tZHoabg";
            } else {
                url = baseUrl + "api/entrypoint-api.bx/page/json/v2?url=" + url + "?layout_container=pdpPage2column&layout_page_index=2&oos_search=false&sh=Ip0tZHoabg";
            }
            funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: url, RequestContentType: "application/json", RequestDataType: "json", RequestData: {}, Async: true, }, tab, function (response) {
                if (response.IsSuccess) {
                    let data = response.Data;
                    var webCharacteristicsdObj = null;
                    var webDescriptionObjs = [];
                    for (var item in data.widgetStates) {
                        if (item.indexOf("webCharacteristics-") > -1) {
                            webCharacteristicsdObj = JSON.parse(data.widgetStates[item]);
                        }
                        if (item.indexOf("webDescription-") > -1) {
                            webDescriptionObjs.push(JSON.parse(data.widgetStates[item]));
                        }
                    }
                    //获取公共参数
                    if (webCharacteristicsdObj && webCharacteristicsdObj.characteristics && webCharacteristicsdObj.characteristics.length > 0) {
                        webCharacteristicsdObj.characteristics.forEach(x => {
                            if (x.short && x.short.length > 0) {
                                x.short.forEach(y => {
                                    if (!content.Parameters.some(z => z.Key == y.name)) {
                                        content.Parameters.push({
                                            Key: y.name,
                                            Value: y.values && y.values.length > 0 ? y.values[0].text : "",
                                        });
                                    }
                                });
                            }
                        });
                    }

                    //多选属性抓取
                    try {
                        let otherParaJson = response.Data.widgetStates["webCharacteristics-3282540-pdpPage2column-2"];
                        let otherPara = JSON.parse(otherParaJson);
                        let longOtherParas = otherPara.characteristics[0].long;
                        for (let k = 0; k < longOtherParas.length; k++) {
                            let longPara = longOtherParas[k];
                            content.Parameters.push({
                                Key: longPara.name,
                                Value: longPara.values.map(item => item.text).join(','),
                            });
                        }
                    } catch (e) { }

                    //获取描述
                    var detailedDescriptionImage = [];
                    webDescriptionObjs.forEach(x => {
                        if (x && x.richAnnotation) {
                            x.richAnnotation = x.richAnnotation.replace(/%/g, '%25');
                            detailedDescription = decodeURIComponent(x.richAnnotation);
                            briefDescription = detailedDescription.replaceAll("<br/>", "\n").replaceAll("<br>", "\n");
                            briefDescription = getSimpleText(briefDescription);
                        }
                        if (x && x.richAnnotationJson && x.richAnnotationJson.content && x.richAnnotationJson.content[0]) {
                            for (var i = 0; i < x.richAnnotationJson.content.length; i++) {
                                if (x.richAnnotationJson.content[i].blocks && x.richAnnotationJson.content[i].blocks != null && x.richAnnotationJson.content[i].blocks.length > 0) {
                                    for (var j = 0; j < x.richAnnotationJson.content[i].blocks.length; j++) {
                                        if (x.richAnnotationJson.content[i].blocks[j] && x.richAnnotationJson.content[i].blocks[j].img && x.richAnnotationJson.content[i].blocks[j].img.src && x.richAnnotationJson.content[i].blocks[j].img.src.length > 0) {
                                            detailedDescriptionImage.push(`<img src="${x.richAnnotationJson.content[i].blocks[j].img.src}">`);
                                            if (!x.richAnnotationJson.content[i].blocks[j].img.position)
                                                x.richAnnotationJson.content[i].blocks[j].img.position = 'width_full';
                                            if (!x.richAnnotationJson.content[i].blocks[j].img.positionMobile)
                                                x.richAnnotationJson.content[i].blocks[j].img.positionMobile = 'width_full';
                                        }

                                    }
                                }
                            }
                            richJson = JSON.stringify(x.richAnnotationJson);
                        }
                    });
                    detailedDescription += detailedDescriptionImage.join("");

                    resolve();
                } else {
                    //resolve();
                    reject(new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！"));
                }
            });
        });
    }

    var getVariantImageDataRecurrence = function () {
        var tasks = [];
        tasks.push(getDescCategoryId());
        var imgLinks = content.SkuLinks.filter(x => !x.ImageUrls).map(x => x.Link);
        for (var i = 0; i < imgLinks.length; i++) {
            tasks.push(getVariantImageData(imgLinks[i]));
        }
        if (requestIndex == 0) {
            tasks.push(getParameterData());
            requestIndex++;
        }
        Promise.all(tasks).then(result => {
            if (content.SkuLinks.some(x => !x.ImageUrls)) {
                getVariantImageDataRecurrence();
            } else {
                saveProductData();
            }
        }).catch(error => {
            funCallback({ "Type": "NotificationClose", "Key": notificationKey }, tab, () => { });
            //异步,无法触发到上层函数的TryCatch,自行提示
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Ozon产品解析失败!" + error.message }, tab, function (response) { });
            throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
        });
    }

    var saveProductData = function () {
        var productInfo = content.Info;
        if (isVariant) {
            content.SkuLinks.forEach(x => {
                x.ImageUrls.forEach(y => {
                    if (!allImages.some(z => z == y))
                        allImages.push(y);
                });
            });
            allImages = Array.from(new Set(allImages));
        } else {
            allImages = content.Skus[0].VariantImageUrl;
        }

        var propertyNames = [];
        content.Skus.forEach(x => {
            x.VariantImageUrl = x.VariantImageUrl.join("|");
            if (x.Property) {
                var property = JSON.parse(x.Property);
                property.forEach(y => {
                    if (!propertyNames.some(z => z == y.Key)) {
                        propertyNames.push(y.Key);
                    }
                });
            }
        })

        if (!detailedDescription) {
            detailedDescription = btoa(encodeURI(productInfo.description))
        }
        if (!briefDescription) {
            briefDescription = getSimpleText(productInfo.description)
        }
        if (richJson && richJson.length > 0) {
            content.Parameters.push({
                Key: "Rich-контент JSON",
                Value: richJson,
            });
        }
        var box =
        {
            "Title": productInfo.name,
            "DetailedDescription": detailedDescription,
            "BriefDescription": briefDescription,
            "ImageUrl": allImages.join("|"),
            "PropertyName": propertyNames.length > 0 ? JSON.stringify(propertyNames) : "[]",
            "PlatformCategoryId": '',
            "SourceUrl": souceUrl,
            "VideoUrl": content.VideoUrl,
            "IsClaimed": false,
            "SourcePlatform": 8,
            "Tags": [],
            "Remark": "",
            "CreateTime": "1900-01-01 00:00:00",
            "Parameters": JSON.stringify(content.Parameters),
            "PlatformCategoryName": content.CategoryName,
            "PlatformCategoryId": descriptionCategoryId,
        };
        funCallback({ "Type": "NotificationClose", "Key": notificationKey }, tab, () => { });
        SaveProduct(tab, { "Box": box, "BoxItem": content.Skus }, funCallback);
    }

    var getDescCategoryId = function () {
        return new Promise(resolve => {
            try {
                let firstSkuCode = content.Skus[0].SkuCode.toString();
                funCallback({ "Type": "GetDocumentCookies", "NeedNameArr": ["contentId", "sc_company_id"] }, tab, function (response) {
                    if (response && ((response.contentId && response.contentId.length > 0) || (response.sc_company_id && response.sc_company_id.length > 0))) {
                        let companyId = '';
                        if (response.contentId && response.contentId.length > 0)
                            companyId = response.contentId.toString();
                        else if (response.sc_company_id && response.sc_company_id.length > 0)
                            companyId = response.sc_company_id.toString();
                        request("https://seller.ozon.ru/api/v1/seller-tree/resolve/by-sku", {
                            method: "POST",
                            responseType: "json",
                            body: { "skus": [firstSkuCode] },
                            headers: {
                                "x-o3-company-id": companyId
                            }
                        }).then(detailResult => {
                            if (detailResult["resolved_categories_by_sku"]
                                && detailResult["resolved_categories_by_sku"][firstSkuCode]
                                && detailResult["resolved_categories_by_sku"][firstSkuCode]["description_category_id_level_3"]
                                && detailResult["resolved_categories_by_sku"][firstSkuCode]["description_type_id"]) {
                                descriptionCategoryId = detailResult["resolved_categories_by_sku"][firstSkuCode]["description_category_id_level_3"] + "-" + detailResult["resolved_categories_by_sku"][firstSkuCode]["description_type_id"];
                            }
                            resolve();
                        }).catch(reason => {
                            resolve();
                        });
                    } else {
                        resolve();
                    }
                });
            } catch (e) {
                resolve();
            }
        });
    }

    //组装数据
    async function startRequest() {
        if (isVariant) {//多变体
            getVariantImageDataRecurrence();
        } else {
            var tasks = [getDescCategoryId(), getParameterData(), getSingleVariantData()];
            Promise.all(tasks).then(result => {
                saveProductData();
            }).catch(error => {
                funCallback({ "Type": "NotificationClose", "Key": notificationKey }, tab, () => { });
                //异步,无法触发到上层函数的TryCatch,自行提示
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Ozon产品解析失败!" + error.message }, tab, function (response) { });
                throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
            })
        }
    }
    startRequest();
}
//==============================

function AnalyticalLazadaProducts(content, tab, souceUrl, funCallback) {

    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    request(souceUrl, {
        responseType: "text"
        , method: "GET"
    }).then(data => {
        typeof (data) == "object" && (data = JSON.stringify(data));
        var model = {
            Html: btoa(encodeURI(data)),
            SourcePlatform: 10,
            SouceUrl: souceUrl
        };
        SaveLiknProduct(tab, model, funCallback);
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
    return;


    var pid = souceUrl.split("/");
    var skuGalleries = [];
    if (Array.isArray(content.skuGalleries)) {
        skuGalleries.push(content.skuGalleries[0]); //首页轮播主图
    } else {
        for (var skuKey in content.skuGalleries) {
            for (let i = 0; i < content.skuGalleries[skuKey].length; i++) {
                skuGalleries.push(content.skuGalleries[skuKey][i]);
            }
            if (skuGalleries.length > 0)
                break;
        }
    }

    var productInfo = content.product;
    var skuBase = content.productOption.skuBase;
    var properties = skuBase.properties;  //拿到变体对应的属性值集合
    var jsonSkus = skuBase.skus;  //获取到属性值与变体之间的对应关系
    var multipleProperties = properties.length > 1;
    var skuInfos = content.skuInfos;
    var deliveryOptions = content.deliveryOptions;
    var tags = [];
    var images = [];
    var skus = [];
    var propertyName = properties.map(x => x.name);
    var skuFreightFee = [];
    var categoryId = skuInfos[0].categoryId;

    //获取变体对应的变体属性
    var skusProperties = [];
    jsonSkus.forEach(function (item) {
        var skuProp = { SkuId: item.skuId, Properties: [] };
        if (item.propPath != null) {
            var propPaths = item.propPath.split(";");
            var propertiesList = [];
            propPaths.forEach(function (pro, intdex) {
                var propertiesName = properties.find(x => x.pid == pro.split(":")[0]).name;
                var propertiesModel = properties.find(x => x.pid == pro.split(":")[0]).values[0].value;
                var propertiesValue = "";
                if (!Array.isArray(propertiesModel))
                    propertiesValue = properties.find(x => x.pid == pro.split(":")[0]).values.find(x => x.vid == pro.split(":")[1]).name;
                else {
                    propertiesValue = properties.find(x => x.pid == pro.split(":")[0]).values[0].value.find(x => x.vid == pro.split(":")[1]).name;
                }
                propertiesList.push({ Key: propertiesName, "Value": propertiesValue });
            });
            skuProp = { SkuId: item.skuId, Properties: propertiesList };
        }
        skusProperties.push(skuProp);
    });
    //主图
    images = skuGalleries.map(x => x.poster);

    //运费
    if (deliveryOptions != null) {
        for (var deliveryKey in deliveryOptions) {
            if (deliveryOptions[deliveryKey].length > 0) {
                skuFreightFee.push({ key: deliveryKey, value: deliveryOptions[deliveryKey][0].feeValue });
            }
        }
    }

    var skuList = [];
    for (var item in skuInfos) {
        if (skuInfos[item] != null && skuList.find(x => x == skuInfos[item].skuId) == null) {
            var property = skusProperties.find(x => x.SkuId == skuInfos[item].skuId);
            var freightFee = skuFreightFee.find(x => x.key == skuInfos[item].skuId);
            var price = 0.0;
            if (skuInfos[item].price && skuInfos[item].price.salePrice && skuInfos[item].price.salePrice != null) {
                price = skuInfos[item].price.salePrice.value;
            }
            var sku = {
                "Property": (null == property || property.Properties == null || 0 >= property.Properties) ? "[]" : JSON.stringify(property.Properties),
                "Price": price,
                "Freight": (freightFee == null || freightFee == null) ? 0.0 : Number(freightFee.value),
                "Currency": (skuInfos[item].dataLayer == null || skuInfos[item].dataLayer.core == null || skuInfos[item].dataLayer.core.currencyCode == null) ? "USD" : skuInfos[item].dataLayer.core.currencyCode,
                "VariantImageUrl": skuInfos[item].image,
                "ShippingWeight": 0.0
            }
            skuList.push(skuInfos[item].skuId);
            skus.push(sku);
        }
    }

    var box =
    {
        "Title": productInfo.title,
        "BriefDescription": productInfo.desc == null ? content.ExtDescText : getSimpleText(productInfo.desc),
        "DetailedDescription": btoa(encodeURI(productInfo.desc)),
        "ImageUrl": images.join('|'),
        "PropertyName": 0 >= propertyName.length ? "[]" : JSON.stringify(propertyName),
        "PlatformCategoryId": categoryId,
        "SourceUrl": productInfo.link,
        "VideoUrl": "",
        "IsClaimed": false,
        "SourcePlatform": 10,
        "Tags": "",
        "Remark": "",
        "CreateTime": "1900-01-01 00:00:00",
        "Parameters": "[]"
    };

    SaveProduct(tab, { "Box": box, "BoxItem": skus }, funCallback);
}

function AnalyticalEbayProducts(content, tab, souceUrl, funCallback, isRetry) {

    if (content == "none" || content == null)
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    let modules = null;
    if (content.productData) {
        for (let index = 0; index < content.productData.length; index++) {
            if (content.productData[index]?.[2]?.model) {
                modules = content.productData[index][2].model.modules;
                break;
            }
        }
    }

    // 第一次没拿到 modules，再根据 sourceUrl 请求一次详情页
    if (modules == null && !isRetry) {
        request(souceUrl, {
            responseType: "text",
            method: "GET"
        }).then(html => {
            funCallback({
                Type: "GetEbayHtmlData",
                html: html
            }, tab, function (ebayData) {
                if (!ebayData || ebayData == "none")
                    throw new Error("未能成功获取到EbayHtml数据！若此错误频繁出现，请联系客服！");
                AnalyticalEbayProducts(ebayData, tab, souceUrl, funCallback, true);
            });
        }).catch(reason => {
            console.error("EBAY request异常：", reason);
            catchFuncallback(reason, funCallback);
        });
        return;
    }

    // 已经重新请求过一次，还是没有 modules
    if (modules == null) throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    //获取描述,请求必须在后台js执行,在前台执行会因跨域问题无法请求成功
    let desurl = modules.ITEM_DESCRIPTION_MIN_VIEW_MODULE.sections[0].action.URL;
    if (desurl == '' && content.htmldesurl)
        desurl = content.htmldesurl

    let OriginalDescription = '';
    let BriefDescription = ''
    let DetailedDescription = ''

    async function callEbayApi() {
        await request(desurl, {
            responseType: "text"
            , method: "GET"
        }).then(res => {
            if (res !== null) {

                //描述截取说明:
                //1.html包含js,需要去除换行再进行匹配
                //2.部分描述br不能替换成换行,不然换行比显示的多了,部分br需要替换换行
                //3.部分描述有tbody,不能对里面的p标签替换成换行
                deshtml = res;
                OriginalDescription = res;
                deshtml = deshtml.replace(/\r\n|\n/g, '')
                deshtml = deshtml.replace(/<title>eBay<\/title>/g, '')
                //deshtml = deshtml.replace(/(?<=(<tbody.*?))<\/p>/g, '')
                deshtml = deshtml.replace(/<\/tr>/g, '\n')
                deshtml = deshtml.replace(/<style[^>]*?>.*?<\/style>/g, '')
                deshtml = deshtml.replace(/<\/span><\/font><\/div>|<\/span><\/div>/g, '\n')
                var strToLong = deshtml.length > 50000;
                //先查找，存在再替换
                var pIndex = deshtml.indexOf("<p");
                if (pIndex >= 0 && !strToLong) {
                    deshtml = deshtml.replace(/(?<=(<p.*?))<br>/g, '\n')
                }

                //先查找，存在再替换
                var tbodyIndex = deshtml.indexOf("<tbody");
                if (tbodyIndex >= 0 && !strToLong) {
                    deshtml = deshtml.replace(/(?<=(<tbody.*?))<\/p>/g, '')
                }

                //deshtml = getSimpleText(deshtml)
                deshtml = deshtml.replace(/^\t*/g, '')
                console.log(res);
                BriefDescription = convertHtmlToPlainText(res)
                // DetailedDescription = cleanHtmlKeepTags(res);

                // DetailedDescription = DetailedDescription.replace(/\n/g, '</p>\n<p>')
                // DetailedDescription = DetailedDescription.replace(/^/g, '<p>')
                // DetailedDescription = DetailedDescription.replace(/$/g, '</p>')
                // DetailedDescription = DetailedDescription.replace(/<p><\/p>|<p>( |\t)*<\/p>/g, '<br>')
                //console.log('获取描述', desurl, res);
            } else {
                console.log('获取描述错误', e);
            }
        }).catch(reason => {
            console.log('获取描述错误', reason);
        });
    }

    callEbayApi().then(res => {
        //获取分类
        let categoryId = ''
        if (desurl && desurl.split("category=").length > 1)
            categoryId = desurl.split("category=")[1].split("&")[0];//切割描述,获取分类Id

        //获取全部图片
        let ImageUrls = modules.PICTURE.mediaList
            .filter(x => x.mediaType === 'IMAGE')   //只保留普通图片，排除视频封面类型的图片
            .map(x => {
                var imgUrl = "";
                if (x.image.zoomImg) {
                    imgUrl = x.image.zoomImg.URL;
                } else if (x.image.originalImg) {
                    imgUrl = x.image.originalImg.URL;
                } else if (x.image.thumbnail) {
                    imgUrl = x.image.thumbnail.URL;
                }
                return imgUrl;
            }).filter(x => x != '');

        //获取全部规格名称
        var PropertyNames = [];
        if (modules.MSKU) {
            for (let menuModel of modules.MSKU.selectMenus) {
                PropertyNames.push(menuModel.displayLabel)
            }
        }

        //获取参数
        var Parameters = []
        var ParametersItems = modules.ABOUT_THIS_ITEM.sections.features.dataItems;//ParametersData.w[0][2].model.sections.features.dataItems
        for (let key in ParametersItems) {
            let dataItem = ParametersItems[key]

            let paskey = dataItem.labels[0].textSpans[0].text
            let pasval = '';

            if (dataItem.values[0].textSpans && dataItem.values[0].textSpans.length > 0)
                pasval = dataItem.values[0].textSpans[0].text
            else if (dataItem.values[0].textualDisplays && dataItem.values[0].textualDisplays.length > 0)
                pasval = dataItem.values[0].textualDisplays[0].textSpans[0].text

            Parameters.push({ Key: paskey, Value: pasval })
        }

        //获取标题
        //let titleText = modules.BIN_NUDGE.itemTitle.textSpans[0].text;
        let titleText = ""
        let TitleModel = modules.TITLE;

        //译文标题
        if (TitleModel.infoOverlay && TitleModel.infoOverlay.messageText)
            titleText = TitleModel.infoOverlay.messageText[0].textSpans[0].text

        //源译文标题
        if (titleText == '' && TitleModel.mainTitle && TitleModel.mainTitle.textSpans)
            titleText = TitleModel.mainTitle.textSpans[0].text

        //初步组装Sku
        let skus = [];
        if (modules.MSKU) {
            for (let key in modules.MSKU.variationsMap) {
                let varItem = modules.MSKU.variationsMap[key]
                let price = 0;
                let currency = '';
                if (varItem.binModel.price.value.convertedFromValue) {
                    price = varItem.binModel.price.value.convertedFromValue
                    currency = varItem.binModel.price.value.convertedFromCurrency
                }
                else {
                    if (varItem.binModel.price.value.value) {
                        price = varItem.binModel.price.value.value
                        currency = varItem.binModel.price.value.currency
                    }
                }
                let sku = {
                    "EbayVariationId": key,
                    "Property": "[]",
                    "Price": price,
                    "Currency": currency,
                    "VariantImageUrl": "",
                    "PropertyTemp": []
                }

                skus.push(sku)
            }
        }

        //组装Sku规格信息
        if (modules.MSKU) {
            for (let menuModel of modules.MSKU.selectMenus) {
                let keyName = menuModel.displayLabel;
                for (let ItemValueId of menuModel.menuItemValueIds) {

                    let menuItem = modules.MSKU.menuItemMap[ItemValueId]

                    let valName = menuItem.valueName;
                    var variantImageUrl = "";
                    if (menuModel.hasPictures && modules.MSKU.menuItemPictureIndexMap) {
                        var menuItemPictureIndexs = modules.MSKU.menuItemPictureIndexMap[ItemValueId];
                        variantImageUrl = ImageUrls.filter((item, index) => menuItemPictureIndexs.indexOf(index) > -1).join("|");
                    }
                    for (let matchingVariationId of menuItem.matchingVariationIds) {
                        let sku = skus.find(x => x.EbayVariationId == matchingVariationId)

                        if (variantImageUrl)
                            sku.VariantImageUrl = variantImageUrl;
                        sku.PropertyTemp.push({ Key: keyName, Value: valName })

                    }
                }
            }
        }
        for (let sku of skus) {
            sku.Property = JSON.stringify(sku.PropertyTemp)

            if (sku.VariantImageUrl == '')
                sku.VariantImageUrl = ImageUrls[0]
        }

        //单品情况
        if (skus.length <= 0) {
            let price = 0;
            let currency = '';
            if (modules.BUY_BOX.binModel) { //一口价
                if (modules.BUY_BOX.binModel.price.value.value.convertedFromValue) {
                    price = modules.BUY_BOX.binModel.price.value.value.convertedFromValue
                    currency = modules.BUY_BOX.binModel.price.value.convertedFromCurrency
                }
                else {
                    if (modules.BUY_BOX.binModel.price.value.value) {
                        price = modules.BUY_BOX.binModel.price.value.value
                        currency = modules.BUY_BOX.binModel.price.value.currency
                    }
                }
            }
            else if (modules.BUY_BOX.bidPrice) //拍卖价
            {
                if (modules.BUY_BOX.bidPrice.value) {
                    price = modules.BUY_BOX.bidPrice.value.value
                    currency = modules.BUY_BOX.bidPrice.value.currency
                }

            }
            skus.push({
                "Property": "[]",
                "Price": price,
                "Currency": currency,
                "VariantImageUrl": ImageUrls.length > 0 ? ImageUrls[0] : [],
            })
        }

        funCallback({ "Type": "CleanHtmlKeepTags", "HtmlStr": OriginalDescription }, tab, function (keepTagResponse) {
            DetailedDescription = keepTagResponse.data;
            let compatibilityData = null;
            let allRows = [];

            //某些商品有适用性表格需要抓取
            if (modules.COMPATIBILITY_TABLE) {
                try {
                    // 1. 定义变量
                    let currentOffset = 0;
                    const limit = 20;

                    // 2. 定义纯 fetch 异步循环函数
                    async function fetchCompatibilityData() {
                        while (true) {
                            const requestUrl = `https://www.ebay.com/g/api/finders?module_groups=PART_FINDER&referrer=VIEWITEM&offset=${currentOffset}&module=COMPATIBILITY_TABLE`;

                            try {
                                console.log(`正在请求第 ${currentOffset / limit + 1} 页...`);

                                // 发起纯粹的 fetch POST 请求
                                const response = await fetch(requestUrl, {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json'
                                    },
                                    body: JSON.stringify({
                                        scopedContext: {
                                            catalogDetails: {
                                                itemId: content.itemId,
                                                categoryId: categoryId
                                            }
                                        }
                                    })
                                });

                                // 检查 HTTP 状态是否成功
                                if (!response.ok) {
                                    throw new Error(`HTTP error! status: ${response.status}`);
                                }

                                // 解析返回的 JSON 数据
                                const result = await response.json();

                                if (compatibilityData == null) {
                                    compatibilityData = result;
                                }

                                // 提取当前页的数据行
                                const tableData = result?.modules?.COMPATIBILITY_TABLE?.paginatedTable;
                                const rows = tableData?.rows || [];

                                // 追加到总数组
                                allRows = allRows.concat(rows);
                                console.log(`本页获取 ${rows.length} 条，累计 ${allRows.length} 条`);

                                // 判断终止条件：如果返回数量小于限制数，说明是最后一页
                                if (rows.length < limit) {
                                    console.log("已到达最后一页，停止请求。");
                                    saveData(allRows);
                                    break; // 退出 while 循环
                                }

                                // 更新偏移量，准备请求下一页
                                currentOffset += limit;

                            } catch (error) {
                                console.error("请求失败:", error);
                                if (allRows.length > 0) {
                                    saveData(allRows);
                                } else {
                                    handleError(error);
                                }
                                break;
                            }
                        }
                    }

                    // 3. 执行异步函数
                    fetchCompatibilityData();

                } catch (e) {
                    console.error("外层异常:", e);
                    saveData();
                }
            } else {
                saveData();
            }

            //保存产品数据 
            function saveData() {

                if (allRows.length > 0 && compatibilityData) {
                    try {
                        compatibilityData.modules.COMPATIBILITY_TABLE.paginatedTable.rows = allRows;
                        let compatibilityTableStr = generateTableString(compatibilityData.modules.COMPATIBILITY_TABLE);
                        DetailedDescription = compatibilityTableStr + DetailedDescription;
                    } catch (e) { }
                }

                //标题有可能存在特殊转义
                titleText = titleText.replace(/<.+?>/g, '')
                titleText = htmlDecodeByRegExp(titleText)
                var box =
                {
                    "Title": titleText,
                    "BriefDescription": BriefDescription,
                    "DetailedDescription": btoa(encodeURI(DetailedDescription)),
                    "ImageUrl": ImageUrls.join('|'),
                    "PropertyName": JSON.stringify(PropertyNames),
                    "PlatformCategoryId": categoryId,
                    "SourceUrl": souceUrl,
                    "SourcePlatform": 13,
                    "Parameters": JSON.stringify(Parameters),
                    "PlatformCategoryName": content.categoryName
                };

                //console.log(box, skus);
                SaveProduct(tab, { "Box": box, "BoxItem": skus }, funCallback);
            }

        });
    });

    function generateTableString(jsonData) {
        const tableData = jsonData?.paginatedTable;

        const headers = tableData.header?.cells || [];
        const rows = tableData.rows || [];

        let headerHtml = "<tr>";
        headers.forEach(header => {
            const text = header?.textSpans?.[0]?.text || "";
            headerHtml += `<th style="border: 1px solid #ccc; padding: 8px;">${text}</th>`;
        });
        headerHtml += "</tr>";

        let rowsHtml = "";
        rows.forEach(row => {
            rowsHtml += "<tr>";
            const cells = row?.cells || [];
            cells.forEach(cell => {
                const text = cell?.textSpans?.[0]?.text || "";
                rowsHtml += `<td style="border: 1px solid #ccc; padding: 8px;">${text}</td>`;
            });
            rowsHtml += "</tr>";
        });

        return `
          <table style="width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; font-size: 14px;">
            <thead>${headerHtml}</thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        `;
    }

}

function AnalyticalTmallProducts(content, tab, souceUrl, originalUrl = '', funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    function ExcuteTmallProductData(tk) {
        if (tk.indexOf('_') > -1)
            tk = tk.split('_')[0];
        var url = new URL(souceUrl);
        var time = new Date().getTime();

        var urlValueArr = souceUrl.split('?')[1],
            abbucket = '',
            id = '',
            rn = '',
            spm = '',
            pvid = '',
            skuId = '',
            utparam = '',
            scm = '',
            priceTId = '',
            ns = '',
            xxc = '';

        if (urlValueArr.length) {
            var urlValueArr = getUrlQuery(urlValueArr);
            if (urlValueArr && urlValueArr != null) {
                if (urlValueArr.hasOwnProperty("rn"))
                    rn = urlValueArr["rn"];
                if (urlValueArr.hasOwnProperty("abbucket"))
                    abbucket = urlValueArr["abbucket"];
                if (urlValueArr.hasOwnProperty("id"))
                    id = urlValueArr["id"];
                if (urlValueArr.hasOwnProperty("spm"))
                    spm = urlValueArr["spm"];
                if (urlValueArr.hasOwnProperty("pvid"))
                    pvid = urlValueArr["pvid"];
                if (urlValueArr.hasOwnProperty("skuId"))
                    skuId = urlValueArr["skuId"];
                if (urlValueArr.hasOwnProperty("utparam"))
                    utparam = urlValueArr["utparam"];
                if (urlValueArr.hasOwnProperty("scm"))
                    scm = urlValueArr["scm"];
                if (urlValueArr.hasOwnProperty("priceTId"))
                    priceTId = urlValueArr["priceTId"];
                if (urlValueArr.hasOwnProperty("ns"))
                    ns = urlValueArr["ns"];
                if (urlValueArr.hasOwnProperty("xxc"))
                    xxc = urlValueArr["xxc"];
            }
        }

        id = id ? id : content.id; //获取url上的id，没有则取节点的值
        var htmlData = JSON.stringify({
            "id": id, //获取url上的id，没有则取节点的值
            "detail_v": "3.3.2", //写死
            "exParams": JSON.stringify({
                "id": id, //获取url上的id，没有则取节点的值
                "pvid": pvid,
                "scm": scm,
                "skuId": skuId,
                "spm": spm, //获取url上的spm
                "utparam": utparam, //获取url上的spm
                "domain": url.origin,
                "path_name": url.pathname,
                "queryParams": url.search.substr(1)
            })
        });
        var detailData = JSON.stringify({
            "id": id,
            "ns": ns,
            "priceTId": priceTId,
            "skuId": skuId,
            "spm": spm, //获取url上的spm
            "utparam": utparam, //获取url上的spm
            "xxc": xxc,
            "detail_v": "3.3.0", //写死
            "preferWireless": true

        });

        var dataSign = getTmallDataSign(tk, time, htmlData);
        var detailSign = getTmallSign(tk, time, detailData);
        var callbackStr = "mtopjsonp15";
        var baseDataUrl = 'https://h5api.m.tmall.com/h5/mtop.taobao.pcdetail.data.get/1.0/?jsv=2.6.1';
        var baseDetailUrl = 'https://h5api.m.tmall.com/h5/mtop.taobao.detail.getdesc/7.0/?'
        if (souceUrl.indexOf('detail.tmall.hk/hk/') > -1 || souceUrl.indexOf('detail.tmall.com/hk/') > -1) {
            baseDataUrl = 'https://h5api.m.tmall.hk/h5/mtop.taobao.pcdetail.data.get/1.0/?jsv=2.6.1';
            callbackStr = "mtopjsonp10";
            baseDetailUrl = 'https://h5api.m.tmall.hk/h5/mtop.taobao.detail.getdesc/7.0/?';
        }
        var dataUrl = baseDataUrl +
            '&appKey=12574478&t=' + time + '&sign=' + dataSign + '&api=mtop.taobao.pcdetail.data.get' +
            '&v=1.0&isSec=0&ecode=0&timeout=10000&dataType=json&valueType=string' +
            '&ttid=2022%40taobao_litepc_9.17.0&AntiFlood=true&AntiCreep=true&preventFallback=true&type=json' +
            '&data=' + escape(htmlData);

        var detailUrl2 = baseDetailUrl +
            'jsv=2.7.4&' +
            'appKey=12574478&' +
            't=' + time + '&' +
            'sign=' + detailSign + '&' +
            'dangerouslySetWindvaneParams=%5Bobject%20Object%5D&' +
            'api=mtop.taobao.detail.getdesc&' +
            'v=7.0&' +
            'AntiFlood=true&' +
            'AntiCreep=true&' +
            'H5Request=true&' +
            'timeout=3000&' +
            'ttid=2022%40tmall_litepc_9.17.0&' +
            'type=jsonp&' +
            'dataType=jsonp&' +
            'callback=' + callbackStr + '&' +
            'data=' + escape(detailData);
        funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: dataUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
            if (response.IsSuccess) {
                var data = response.Data;
                if (data === null || data.data === null || data.data === {} || data.data.item === undefined || data.data.item === null) {
                    //有验证码需滑动验证码
                    if (data &&
                        data.data &&
                        data.data.url &&
                        data.data.url != null) {
                        funCallback({ "Type": "ShowTmallVerifyBox", "BoxHtml": '<iframe src="' + data.data.url + '"' + ' style="width: 100%; height: 300px;" scrolling="auto" frameborder="0"></iframe>' }, tab, function (response) { });
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "天猫采集被拦截！请滑动验证码！" }, tab, function (response) { });
                    } else {
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集数据为空，请稍后重试！" }, tab, function (response) { });
                    }

                    funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
                    return;
                }

                var model = {
                    Html: btoa(encodeURI(JSON.stringify(data.data))),
                    SourcePlatform: 15,
                    SouceUrl: originalUrl == '' ? souceUrl : originalUrl
                };
                //请求完SKU信息，再继续请求图文描述，图文描述如果请求失败，可以忽略
                try {
                    funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: detailUrl2, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "text", RequestData: {}, }, tab, function (response) {
                        if (response.IsSuccess) {
                            var data = response.Data;
                            let resultData = data.split(callbackStr + '(')[1].slice(0, -1);
                            if (resultData &&
                                resultData.indexOf('data') > -1 &&
                                resultData.indexOf('data') > -1 &&
                                resultData.indexOf('components') > -1 &&
                                resultData.indexOf('componentData') > -1) {
                                let resultData2 = JSON.parse(resultData);
                                model.MoreData = JSON.stringify(resultData2.data);
                            }
                            SaveLiknProduct(tab, model, funCallback);
                        } else {
                            SaveLiknProduct(tab, model, funCallback);
                        }
                    });
                } catch (e) {
                    console.log("err:", e)
                    SaveLiknProduct(tab, model, funCallback);
                }
            } else {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "天猫采集被拦截！请刷新天猫页面重试！" }, tab, function (response) { });
                funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
        });
    }

    //本地缓存Token获取天猫产品（适用于批量采集）
    function ExcuteTmallProductDataByLocalTk() {
        chrome.storage.local.get(['wyystmallh5tk'], function (result) {
            var tk = result.wyystmallh5tk;
            ExcuteTmallProductData(tk);
        });
    }

    funCallback({ "Type": "GetDocumentCookies", "NeedNameArr": ["_m_h5_tk"] }, tab, function (response) {
        if (response && response._m_h5_tk && response._m_h5_tk.length > 0) {
            ExcuteTmallProductData(response._m_h5_tk);
        } else {
            chrome.storage.local.get(['wyystmallh5tk'], function (result) {
                var tk = result.wyystmallh5tk;
                if (!tk) {//凭据不存在就调用下接口，会自动刷新凭证
                    request("https://h5api.m.tmall.com/h5/mtop.taobao.pcdetail.data.get/1.0/?jsv=2.6.1&appKey=12574478&t=1704881502814", {
                        method: "GET",
                        responseType: "json"
                    }).then(data => {
                        ExcuteTmallProductDataByLocalTk();
                    }).catch(reason => {
                        ExcuteTmallProductDataByLocalTk();
                    });
                } else {
                    ExcuteTmallProductDataByLocalTk();
                }
            });
        }
    });
    return;
}

function AnalyticalCouPangProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("获取sku信息失败！");

    var descList = "";
    var deshtml = "";
    var DetailedDescription = "";
    if (content.sellingInfoVo.sellingInfo != null) {
        descList = content.sellingInfoVo.sellingInfo.join("\r\n");
    }

    var skus = [];
    var PropertyNameStr = "";
    if (content.options != null) {
        PropertyNameStr = JSON.stringify(content.options.optionRows.map(x => x.name));
        var variantList = content.options.optionRows;
        var varList = [];
        //获取变体属性
        varList = variantList.map(x => {
            var variantData = {};
            variantData.Name = x.name;
            variantData.attributes = x.attributes.map(varl => {
                return { key: varl.valueId, value: varl.name };
            });
            //varList.push(variantData);
            return variantData;
        });
        //var skuMapNames = content.options.optionRows;
        for (const x in content.options.attributeVendorItemMap) {
            var sku = {};
            var skyKey = x;
            var variantListData = skyKey.split(':');
            var propertys = [];
            var imgUrl = content.options.attributeVendorItemMap[x].images[0].origin;
            for (let i = 0; i < variantListData.length; i++) {
                //var property = {};
                var propKey = "";
                var propValue = "";
                for (let j = 0; j < varList.length; j++) {
                    for (let k = 0; k < varList[j].attributes.length; k++) {
                        if (varList[j].attributes[k].key == variantListData[i]) {
                            propKey = varList[j].Name;
                            propValue = varList[j].attributes[k].value;
                            propertys.push({ key: propKey, value: propValue });
                            break;
                        }
                    }

                    if (propKey != "") {
                        break;
                    }
                }
            }

            sku.Property = JSON.stringify(propertys);
            if (content.options.attributeVendorItemMap[x].quantityBase[0].price.i18nSalePrice != null &&
                content.options.attributeVendorItemMap[x].quantityBase[0].price.i18nSalePrice.amount != null) {
                sku.Price = content.options.attributeVendorItemMap[x].quantityBase[0].price.i18nSalePrice.amount;
                sku.Currency = content.options.attributeVendorItemMap[x].quantityBase[0].price.i18nSalePrice.currency;
            } else if (content.options.attributeVendorItemMap[x].quantityBase[0].price.i18nCouponPrice != null) {
                sku.Price = content.options.attributeVendorItemMap[x].quantityBase[0].price.i18nCouponPrice.amount;
                sku.Currency = content.options.attributeVendorItemMap[x].quantityBase[0].price.i18nCouponPrice.currency;
            }
            sku.Freight = 0;
            sku.VariantImageUrl = imgUrl;
            sku.ShippingWeight = 0.00;
            skus.push(sku);
        }
    } else {
        var sku = {};
        var propertys = [];
        var imgUrl = content.images[0].origin;
        sku.Property = JSON.stringify(propertys);
        sku.Price = content.quantityBase[0].price.i18nSalePrice.amount;
        sku.Freight = 0;
        sku.Currency = content.quantityBase[0].price.i18nSalePrice.currency;
        sku.VariantImageUrl = imgUrl;
        sku.ShippingWeight = 0.00;
        skus.push(sku);
    }

    if (content.apiUrlMap != null && content.apiUrlMap.addToCartUrl != null) {
        var spUrl = content.apiUrlMap.addToCartUrl.split('&');
        var urlProductId = "";
        var urlItems = "";
        var urlVendoritems = "";
        for (let i = 0; i < spUrl.length; i++) {
            if (urlProductId != "" && urlItems != "" && urlVendoritems != "")
                break;

            if (urlItems == "" && spUrl[i].indexOf('?itemId=') > -1) {
                urlItems = spUrl[i].split('?itemId=')[1];
            }

            if (urlProductId == "" && spUrl[i].indexOf('productId=') > -1) {
                urlProductId = spUrl[i].split('productId=')[1];
            }

            if (urlVendoritems == "" && spUrl[i].indexOf('vendorItemId=') > -1) {
                urlVendoritems = spUrl[i].split('vendorItemId=')[1];
            }
        }
    }

    var descUrl = 'https://www.coupang.com/vp/products/' + urlProductId + '/items/' + urlItems + '/vendoritems/' + urlVendoritems;

    funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: descUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
        if (response.IsSuccess) {
            let res = response.Data
            try {
                if (res !== null) {

                    //描述截取说明:
                    //1.html包含js,需要去除换行再进行匹配
                    //2.部分描述br不能替换成换行,不然换行比显示的多了,部分br需要替换换行
                    //3.部分描述有tbody,不能对里面的p标签替换成换行
                    var lableList = [];
                    if (res.essentials != null && res.essentials.length > 0) {
                        lableList = res.essentials.map(x => {
                            return x.title + ':' + x.description;
                        });
                    }

                    var htmlStr = ""
                    if (res.details != null && res.details.length > 0) {
                        var descListData = res.details.map(x => {
                            if (x.vendorItemContentDescriptions[0].imageType) {
                                return '<img src="' + x.vendorItemContentDescriptions[0].content + '"/>';
                            } else {
                                return x.vendorItemContentDescriptions[0].content;
                            }
                        });
                        htmlStr = descListData.join('\r\n');
                    }
                    var oriDesc = descList + '\r\n' + lableList.join('\r\n') + htmlStr;
                    deshtml = oriDesc;
                    deshtml = deshtml.replace(/\r\n|\n/g, '')
                    deshtml = deshtml.replace(/<title>eBay<\/title>/g, '')
                    deshtml = deshtml.replace(/(?<=(<p.*?))<br>/g, '\n')
                    deshtml = deshtml.replace(/(?<=(<tbody.*?))<\/p>/g, '')
                    deshtml = deshtml.replace(/<\/tr>/g, '\n')
                    deshtml = deshtml.replace(/<style[^>]*?>.*?<\/style>/g, '')
                    deshtml = deshtml.replace(/<\/span><\/font><\/div>|<\/span><\/div>/g, '\n')
                    deshtml = getSimpleText(deshtml)
                    deshtml = deshtml.replace(/^\t*/g, '')

                    BriefDescription = convertHtmlToPlainText(oriDesc) + htmlStr;
                    DetailedDescription = BriefDescription
                    DetailedDescription = DetailedDescription.replace(/\n/g, '</p>\n<p>')
                    DetailedDescription = DetailedDescription.replace(/^/g, '<p>')
                    DetailedDescription = DetailedDescription.replace(/$/g, '</p>')
                    DetailedDescription = DetailedDescription.replace(/<p><\/p>|<p>( |\t)*<\/p>/g, '<br>')
                    //console.log('获取描述', desurl, res);
                } else { }
            } catch (e) {
                console.log('获取描述错误', e);
            }

            var imageUrls = content.images.map(x => {
                if (x.origin.indexOf("https:") != 0)
                    return "https:" + x.origin;
                else
                    return x.origin;
            });

            var categoryId = '';
            if (content.leafCategoryInfo
                && content.leafCategoryInfo != null
                && content.leafCategoryInfo.categoryId != null)
                categoryId = content.leafCategoryInfo.categoryId;

            var productInfo = {};
            productInfo.Title = content.itemName;
            productInfo.BriefDescription = convertHtmlToPlainText(oriDesc);
            productInfo.DetailedDescription = DetailedDescription;
            productInfo.ImageUrl = imageUrls.join('|');
            productInfo.PropertyName = PropertyNameStr;
            productInfo.CategoryId = categoryId; //忽略
            productInfo.SourceUrl = souceUrl;
            productInfo.VideoUrl = "";
            productInfo.IsClaimed = false;
            productInfo.SourcePlatform = 16;
            productInfo.Tags = "";
            productInfo.Remark = "";
            productInfo.CreateTime = "1900-01-01 00:00:00";
            productInfo.Parameters = []; //忽略  
            productInfo.PlatformCategoryName = '';
            if (content.leafCategoryInfo != null && content.leafCategoryInfo.parentsCategoryNames != null && content.leafCategoryInfo.parentsCategoryNames.length > 0) {
                productInfo.PlatformCategoryName = content.leafCategoryInfo.parentsCategoryNames[0];
            }

            SaveProduct(tab, { "Box": productInfo, "BoxItem": skus }, funCallback);
        } else {
            CategroyErrorCall("采集失败！若此错误频繁出现，请联系客服！", tab, funCallback);
        }
    });
}

function AnalyticalShopeeProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    var model = {
        Html: btoa(encodeURI(content)),
        SourcePlatform: 9,
        SouceUrl: souceUrl
    };
    if (content.isBathCollect) {
        request(souceUrl, {
            responseType: "text"
            , method: "GET"
        }).then(data => {
            typeof (data) == "object" && (data = JSON.stringify(data));
            var jsonData = '';
            if (data.indexOf('initialState')) {
                jsonData = JSON.parse(data.split('"initialState":')[1].split(',"featureToggles"')[0] + '}');

                model.Html = btoa(encodeURI(JSON.stringify({ data: jsonData.DOMAIN_PDP.data.PDP_BFF_DATA.cachedMap[jsonData.DOMAIN_PDP.data.PDP_BFF_DATA.currentKey] })))
                SaveLiknProduct(tab, model, funCallback);
            } else {
                SaveLiknProduct(tab, model, funCallback);
            }

        }).catch(reason => {
            catchFuncallback(reason, funCallback)
        });
    } else {
        SaveLiknProduct(tab, model, funCallback);
    }

    return;
}

function AnalyticalJDProducts(content, tab, souceUrl, funCallback) {
    if (!content || content == "none" || !content.pageData)
        throw new Error("获取产品信息失败！");

    SaveProduct(tab, { "Box": content.pageData.box, "BoxItem": content.pageData.variantArr }, funCallback);

    // request(souceUrl, {
    //     responseType: "text"
    //     , method: "GET"
    // }).then(data => {
    //     typeof (data) == "object" && (data = JSON.stringify(data));
    //     console.log("data", data);
    //     var model = {
    //         Html: btoa(encodeURI(data)),
    //         SourcePlatform: 18,
    //         SouceUrl: souceUrl,
    //         MoreData: JSON.stringify(content.pageData),
    //         Price: content?.pageData?.price ?? 0
    //     };
    //     SaveLiknProduct(tab, model, funCallback);
    // }).catch(reason => {
    //     catchFuncallback(reason, funCallback)
    // });
    // return;

    // var skus = [];
    // var variantName = [];
    // var skuMapNames = content.product.colorSize;

    // var imageUrls = content.product.imageList.map(x => {
    //     if (x.indexOf("https://img13.360buyimg.com/n1/s350x467_") != 0)
    //         return "https://img13.360buyimg.com/n1/s350x467_" + x;
    //     else
    //         return x;
    // });
    // if (skuMapNames && skuMapNames.length > 0) {
    //     skuMapNames.map(x => {
    //         var sku = {};
    //         var propertys = [];
    //         var imgUrl = "";
    //         for (let key in x) {
    //             if (key != 'skuId') {
    //                 if (!variantName.includes(key)) {
    //                     variantName.push(key);
    //                 }
    //                 var property = {};
    //                 property.Key = key;
    //                 property.value = x[key];
    //                 propertys.push(property);
    //                 if (imgUrl == "") {
    //                     content.varUrl.forEach(vurl => {
    //                         if (vurl.key == property.value) {
    //                             imgUrl = vurl.value;
    //                             return false;
    //                         }
    //                     });
    //                 }
    //             }
    //         }
    //         sku.Property = JSON.stringify(propertys);
    //         sku.Price = content.price;
    //         sku.Freight = 0;
    //         sku.Currency = "CNY";
    //         sku.VariantImageUrl = imgUrl;
    //         sku.ShippingWeight = 0.00;
    //         skus.push(sku);
    //     });
    // } else {
    //     var sku = {};
    //     sku.Property = "[]";
    //     sku.Price = content.price;
    //     sku.Freight = 0;
    //     sku.Currency = "CNY";
    //     sku.VariantImageUrl = (imageUrls && imageUrls.length > 0) ? imageUrls[0] : "";
    //     sku.ShippingWeight = 0.00;
    //     skus.push(sku);
    // }

    // var productInfo = {};
    // productInfo.Title = content.product.name;
    // productInfo.BriefDescription = getSimpleText(content.descStr + content.descimg);
    // productInfo.DetailedDescription = content.descStr + content.descimg;
    // productInfo.ImageUrl = imageUrls.join('|');
    // productInfo.PropertyName = JSON.stringify(variantName.map(x => x));
    // productInfo.CategoryId = "" //忽略
    // productInfo.SourceUrl = souceUrl;
    // productInfo.VideoUrl = "";
    // productInfo.IsClaimed = false;
    // productInfo.SourcePlatform = 18;
    // productInfo.Tags = "";
    // productInfo.Remark = "";
    // productInfo.CreateTime = "1900-01-01 00:00:00";
    // productInfo.Parameters = []; //忽略  

    // SaveProduct(tab, { "Box": productInfo, "BoxItem": skus }, funCallback);
}

function AnalyticalWalmartProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    //请求页面
    request(souceUrl, {
        responseType: "text"
        , method: "GET"
    }).then(data => {
        typeof (data) == "object" && (data = JSON.stringify(data));
        var model = {
            Html: btoa(encodeURI(data)),
            SourcePlatform: 19,
            SouceUrl: souceUrl
        };
        SaveLiknProduct(tab, model, funCallback);
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });

}

function AnalyticalBanggoodProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    let productId = null;
    if (souceUrl) {
        const part = souceUrl.split(".html")[0]; // 分割 .html
        if (part) {
            const segments = part.split("-"); // 分割 -
            if (segments.length > 0) {
                productId = segments.pop(); // 取最后一个
            }
        }
    }

    //请求页面
    request(souceUrl, {
        responseType: "text"
        , method: "GET"
    }).then(pageData => {
        typeof (pageData) == "object" && (data = JSON.stringify(pageData));

        //调用方法获取Language
        funCallback({ "Type": "GetBanggoodProductLanguage", "HtmlStr": pageData }, tab, function (response) {
            let language = response.data;
            let requestImgUrl = `https://m.banggood.com/ajax/product/getProduct/1025803.html?c=api&product_id=${productId}`;
            let requestDescUrl = `https://m.banggood.com/cdn.html?com=product&t=getProductDesc&language=${language}&lang=${language}&c=api&product_id=${productId}`;

            //请求图片
            request(requestImgUrl, {
                responseType: "text"
                , method: "GET"
            }).then(imgData => {

                let moreData = {
                    "ImgData": imgData,
                }

                //请求描述
                request(requestDescUrl, {
                    responseType: "text"
                    , method: "GET"
                }).then(descData => {
                    moreData.DescData = descData;
                    const fbMatch = pageData.match(/"value":([\d.]+)/);
                    var boxPrice = 0;
                    if (fbMatch) {
                        const price = fbMatch[1];
                        const poaMatch = pageData.match(/J-selpoa["'][^>]*value="([^"]+)"/);
                        if (poaMatch) {
                            const poa = poaMatch[1];
                            const warehouseMatch = pageData.match(/J-warehouse["'][^>]*value="([^"]+)"/);
                            if (warehouseMatch) {
                                const warehouse = warehouseMatch[1];
                                request(`https://www.banggood.com/index.php?com=coupon&t=getCouponForGet&products_id=${productId}&poa=${poa}&warehouse=${warehouse}&final_price=${price}`, {
                                    responseType: "json"
                                    , method: "GET"
                                }).then(priceReposon => {
                                    var modelPrice = 0;
                                    if (priceReposon.data.new_user_bonus_info == null)
                                        modelPrice = price;
                                    else
                                        modelPrice = priceReposon.data.new_user_bonus_info.new_user_price.match(/[\d.]+/)[0];

                                    var model = {
                                        Html: btoa(encodeURI(pageData)),
                                        SourcePlatform: 20,
                                        SouceUrl: souceUrl,
                                        Price: modelPrice,
                                        MoreData: JSON.stringify(moreData),
                                    };
                                    SaveLiknProduct(tab, model, funCallback);
                                })
                            }
                        }
                    }
                }).catch(reason => {
                    moreData.DescData = "";
                    var model = {
                        Html: btoa(encodeURI(pageData)),
                        SourcePlatform: 20,
                        SouceUrl: souceUrl,
                        MoreData: JSON.stringify(moreData),
                    };
                    SaveLiknProduct(tab, model, funCallback);
                });
            }).catch(reason => {
                catchFuncallback(reason, funCallback)
            });
        });
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
}

function AnalyticalTemuProducts(content, tab, souceUrl, funCallback) {
    if (content == "none" || content.Ext == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    if (content.DocType == 'type_1_type') {
        //这里做一层驼峰命名转换，后端处理简便点、
        content.Ext = JSON.parse(content.Ext);
        content.Ext.review = null;
        content.Ext = JSON.stringify(convertKeysToCamelCase(content.Ext));
        var model = {
            Html: btoa(encodeURI(content.Ext)),
            SourcePlatform: 21,
            SouceUrl: souceUrl
        };
        SaveLiknProduct(tab, model, funCallback);
    } else {

        // let url2 = "https://www.temu.com/api/oak/integration/render?is_back=1"

        // let headerObj =  {
        //     'accept': 'application/json, text/plain, */*',
        //     'accept-language': 'zh-CN,zh;q=0.9',
        //     'anti-content': '0aqAfxn5IjI8y99ami1pl5EU1spc4MEyfnljKAu0b55857EXEDPzsFkGhGslMt_YOteZY83zN51uZNd9OFGKj0S7UIzD4-yWy_J8O9qSGYFhmWho7O_9t0oiWhM5pcO463cqn48oQhZSrE0DS1qO7jT7wTZtdzRkaVttvJ_At16kzxEPUpMfPiE-K9YpKstE3IUZtWfBPvNtHXPtmP3FdCacWPexRdL5AUtF2UGU_2_yZa2ZsXZP3SVpIPaw_gwfBwxVceX4fIwgTfqxINBVNOMM3L8OL8t3YUEby1Ok-QHcX5yDGn-EiAapTqJsbW2-JWkne-a8Ap3e71mYVMMa62y0gO0FSa_FmlA0y8HbY8btFar0jLLuVMzVA2y_XNLp21l3A-z4ycuOMqmWTU3cL0onTyhy5fHwnM1h-skFSr7CZWUMBpHJ8ww4UwXcBVX9cs79RxWfhrDqMYT-W_-hzkJvwci-VJjwtAFIhLDqQZZgAn-d4gn3FDD_WyS-lAc1SNQ0-bJhaTRGGR2VJhosb0NF4diOaF1q',
        //     'cache-control': 'no-cache',
        //     'content-type': 'application/json;charset=UTF-8',
        //     'origin': 'https://www.temu.com',
        //     'pragma': 'no-cache',
        //     'priority': 'u=1, i',
        //     'referer': 'https://www.temu.com/1pc-fashionable-womens-long-clutch-wallet-with-wristlet-geometric-pattern--leather-large-capacity-zippered-handbag-with-tassel-polyester-lined-stylish-versatile-phone-pouch-g-601099754095187.html?_oak_mp_inf=ENOExYqn1ogBGiBkZTZkMDJlNWJhYzk0NzQxYWU2MTNhNWFlMzAwY2NkYSDOrf%2BV2TI%3D&top_gallery_url=https%3A%2F%2Fimg.kwcdn.com%2Fproduct%2Fopen%2F1fcf21e02d9f4a7c9f25c024e9bf6966-goods.jpeg&spec_gallery_id=2748010007&detailDealsRecEnable=true&refer_page_sn=10009&refer_source=0&freesia_scene=2&_oak_freesia_scene=2&_oak_rec_ext_1=NDc1&bottom_rec_bypass=%7B%22disableDealsTab%22%3A%22false%22%7D&search_key=%E9%92%B1%E5%8C%85%E5%A5%B3&refer_page_el_sn=200049&refer_page_name=search_result&refer_page_id=10009_1741922283589_qr2w8b3udi&_x_sessn_id=pl4d6cnpv7&__csr=1&__torl=&is_back=1',
        //     'sec-ch-ua': '"Not(A:Brand";v="99", "Google Chrome";v="133", "Chromium";v="133"',
        //     'sec-ch-ua-mobile': '?0',
        //     'sec-ch-ua-platform': '"Windows"',
        //     'sec-fetch-dest': 'empty',
        //     'sec-fetch-mode': 'cors',
        //     'sec-fetch-site': 'same-origin',
        //     'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
        //     'verifyauthtoken': 'Ct5lAroFvAWk5pXdHmCEfA9acd67ecc35b825b7'
        //   };

        // let requestObj =JSON.stringify( {
        //     "goods_id": "601099754095187",
        //     });

        // funCallback({ Type: "GetAjaxResult", Async: true, RequestMethod: "POST", RequestHeaders: headerObj, RequestUrl: url2, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: requestObj, }, tab, function (response)
        // {
        //     if(response.IsSuccess)
        //     {
        //         SaveLiknProduct(tab, model, funCallback);
        //     } else {
        //         SaveLiknProduct(tab, model, funCallback);
        //     }
        // });

        //请求页面
        request(souceUrl, {
            responseType: "text"
            , method: "GET",
        }).then(data => {
            // console.log("Temu",data);
            // let aa1 =  data.split("window.rawData=")[1].split(";document.dispatchEvent")[0];
            // let aa2 =  JSON.parse(aa1);
            // let aa3 =  JSON.stringify(aa2);
            // console.log("TemuObj",data);
            //console.log("TemuJson",data);
            let jsonData = data.split("window.rawData=")[1].split(";document.dispatchEvent")[0];
            try {
                let objData = JSON.parse(jsonData);
                if (!objData?.goods && !objData?.store?.goods)
                    if (true)
                        throw new Error("未获取到产品数据");

                if (!objData?.store?.goods?.goodsProperty) {
                    jsonData = content.Ext.split("window.rawData=")[1].split(";document.dispatchEvent")[0];
                    objData = JSON.parse(jsonData);
                    if (!objData?.store?.goods?.goodsProperty) {
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "因平台限制，列表快速采集不稳定，请访问商品详情页面进行采集" }, tab, function (response) { });
                        return;
                    }
                }
            } catch (e) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "因平台限制，列表快速采集不稳定，请访问商品详情页面进行采集" }, tab, function (response) { });
                return;
            }

            typeof (data) == "object" && (data = JSON.stringify(data));
            var model = {
                Html: btoa(encodeURI(jsonData)),
                SourcePlatform: 21,
                SouceUrl: souceUrl
            };
            SaveLiknProduct(tab, model, funCallback);
        }).catch(reason => {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "因平台限制，列表快速采集不稳定，请访问商品详情页面进行采集" }, tab, function (response) { });
            // reason.message='因平台限制，列表快速采集不稳定，请访问商品详情页面进行采集';
            //  catchFuncallback(reason, funCallback)

        });
    }
}
function AnalyticalYiwugoProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    //请求页面
    request(souceUrl, {
        responseType: "text"
        , method: "GET"
    }).then(data => {
        typeof (data) == "object" && (data = JSON.stringify(data));
        var model = {
            Html: btoa(encodeURI(data)),
            SourcePlatform: 23,
            SouceUrl: souceUrl
        };
        SaveLiknProduct(tab, model, funCallback);
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
}
function AnalyticalVVicProducts(content, tab, sourceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    const urlInfo = sourceUrl.split("/");

    if (urlInfo && urlInfo.length > 0) {
        const vid = urlInfo[urlInfo.length - 1].split("?")[0];
        var url = `https://www.vvic.com/apif/item/${vid}/detail`
        //请求接口数据
        request(url, {
            responseType: "json"
            , method: "GET"
        }).then(data => {
            typeof (data) == "object" && (data = JSON.stringify(data));
            var model = {
                Html: data,
                SourcePlatform: 24,
                SouceUrl: sourceUrl
            };
            SaveLiknProduct(tab, model, funCallback);
        }).catch(reason => {
            catchFuncallback(reason, funCallback)
        });
    }

}


function AnalyticalSooxieProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    //请求页面
    request(souceUrl, {
        responseType: "text"
        , method: "GET"
    }).then(data => {
        typeof (data) == "object" && (data = JSON.stringify(data));
        var model = {
            Html: btoa(encodeURI(data)),
            SourcePlatform: 25,
            SouceUrl: souceUrl
        };
        SaveLiknProduct(tab, model, funCallback);
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
}
function AnalyticalDunhuangProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    //请求页面
    request(souceUrl, {
        responseType: "t" +
            "ext"
        , method: "GET"
    }).then(data => {
        typeof (data) == "object" && (data = JSON.stringify(data));
        var model = {
            Html: btoa(encodeURI(data)),
            SourcePlatform: 26,
            SouceUrl: souceUrl
        };

        SaveLiknProduct(tab, model, funCallback);
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
}
function AnalyticalCdiscountProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    productInfo = {};
    images = [];
    skus = [];
    propertyName = [];
    freight = 0;

    descriptionStr = '';
    if (content.descHtml != undefined) {
        descriptionStr = content.descHtml;
    }
    description = '';
    if (content.descHtml != undefined) {
        description = content.descHtml;
    }

    if (description != undefined)
        descriptionHtml = description;

    if (descriptionStr != undefined) {
        descriptionStr = descriptionStr.replace(/ {2,}/g, ' ').replace(/(\r?\n){2,}/g, '\n'); // 多个空格替换为一个空格  多个换行替换为一个换行
        descriptionStr = descriptionStr.replace(/<script>.*?<\/script>/g, "");
    }

    description = description.replace(/ {2,}/g, ' ').replace(/(\r?\n){2,}/g, '\n'); // 多个空格替换为一个空格  多个换行替换为一个换行
    productInfo.DetailedDescription = btoa(encodeURI(description));

    //组合变体获取笛卡尔集
    var propertyList = [];
    if (content.vantList && content.vantList.length > 0) {
        content.vantList.forEach(x => {
            propertyList.push(x);
        });
    }
    // 只保留数字、点 
    content.price = content.price.replaceAll('€', '.').replaceAll(',', '.').replace(/[^\d.]/g, '');

    var skuEscartes = escartesByCdiscount(propertyList);
    if (skuEscartes != null && skuEscartes.PropertyName != null && skuEscartes.PropertyName.length > 0)
        propertyName = skuEscartes.PropertyName;

    //主图
    images = content.mainImg;

    if (skuEscartes != null && skuEscartes.Skus != null && skuEscartes.Skus.length > 0) {
        skuEscartes.Skus.map(x => {
            var sku = {};
            sku.Property = JSON.stringify(x.Property);
            sku.Price = content.price;
            sku.Freight = 0;
            sku.Currency = "USD";
            sku.VariantImageUrl = x.VariantImageUrl.join('|');
            sku.ShippingWeight = 0.00;
            skus.push(sku);
        });
    } else {
        var sku = {};
        sku.Property = JSON.stringify([]);
        sku.Price = content.price;
        sku.Freight = 0;
        sku.Currency = "USD";
        sku.VariantImageUrl = images[0];
        sku.ShippingWeight = 0.00;
        skus.push(sku);
    }

    //补偿单变体可能没有图片,使用主图
    if (skus && skus.length > 0 && !skus[0].VariantImageUrl && images.length > 0)
        skus[0].VariantImageUrl = images[0]

    productInfo.Title = htmlDecodeByRegExp(content.title);
    productInfo.BriefDescription = convertHtmlToPlainText(descriptionStr);
    productInfo.ImageUrl = images.join('|');
    productInfo.PropertyName = JSON.stringify(propertyName);
    productInfo.CategoryId = "";//忽略
    productInfo.SourceUrl = souceUrl;
    productInfo.VideoUrl = "";
    productInfo.IsClaimed = false;
    productInfo.SourcePlatform = 17;
    productInfo.Tags = "";
    productInfo.Remark = "";
    productInfo.CreateTime = "1900-01-01 00:00:00";
    productInfo.Parameters = JSON.stringify(content.descStr.map(x => { return { "Key": x.Key.replaceAll("\n", ""), "Value": x.Value.replaceAll("\n", "") } }));//忽略  //JSON.stringify(parameters)
    productInfo.PlatformCategoryName = content.categoryName;

    //console.log('Data', productInfo, skus);
    SaveProduct(tab, { "Box": productInfo, "BoxItem": skus }, funCallback);
}

function AnalyticalTuGouProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    //请求页面
    if (souceUrl.indexOf('https') !== -1) {
        souceUrl = souceUrl.replace('https', 'http');
    } else if (souceUrl.indexOf('go2.cn') === -1) {
        souceUrl = 'http://www.go2.cn' + souceUrl;
    }
    request(souceUrl, {
        responseType: "text"
        , method: "GET"
    }).then(data => {
        typeof (data) == "object" && (data = JSON.stringify(data));
        var model = {
            Html: btoa(encodeURI(data)),
            SourcePlatform: 28,
            SouceUrl: souceUrl
        };
        SaveLiknProduct(tab, model, funCallback);
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
}
function AnalyticalWSYProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    //请求页面
    request(souceUrl, {
        responseType: "text"
        , method: "GET"
    }).then(data => {
        typeof (data) == "object" && (data = JSON.stringify(data));
        var model = {
            Html: btoa(encodeURI(data)),
            SourcePlatform: 29,
            SouceUrl: souceUrl
        };
        SaveLiknProduct(tab, model, funCallback);
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
}
function AnalyticalETSYroducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: souceUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "html", RequestData: {}, }, tab, function (response) {
        if (response.IsSuccess) {
            var html = response.Data;
            //console.log(JSON.stringify(response.Data.data));
            typeof (html) == "object" && (data = JSON.stringify(html));
            var model = {
                Html: btoa(encodeURI(html)),
                SourcePlatform: 30,
                SouceUrl: souceUrl
            };
            SaveLiknProduct(tab, model, funCallback);
        }
    });
}

function AnalyticalGIGAB2BProducts(content, tab, sourceUrl, funCallback) {
    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    const productId = new URLSearchParams(sourceUrl).get('product_id');
    let productUrl = `https://www.gigab2b.com/index.php?route=/product/info/info/baseInfos&product_id=${productId}`;
    let priceUrl = `https://www.gigab2b.com/index.php?route=/product/info/price/list&product_id=${productId}`;

    let productObj;
    let priceObj;
    let isError = false;

    let saveProduce = function () {
        if (productObj && priceObj) {
            let requestData = {
                product: productObj,
                price: priceObj,
            }
            let model = {
                Html: JSON.stringify(requestData),
                SourcePlatform: 36,
                SouceUrl: sourceUrl
            };
            SaveLiknProduct(tab, model, funCallback);
        }
    }
    request(productUrl, {
        responseType: "json"
        , method: "GET"
    }).then(data => {
        productObj = data.data;
        saveProduce();
    }).catch(reason => {
        if (!isError) {
            isError = true;
            catchFuncallback(reason, funCallback)
        }
    });
    request(priceUrl, {
        responseType: "json"
        , method: "GET"
    }).then(data => {
        priceObj = data.data;
        saveProduce();
    }).catch(reason => {
        if (!isError) {
            isError = true;
            catchFuncallback(reason, funCallback)
        }
    });
}

//小红书
function AnalyticalRedBookProducts(content, tab, sourceUrl, funCallback) {
    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    // 定义正则表达式
    const regex = /\/goods-detail\/([a-f0-9]{24})(?:\?|$)/;

    // 使用正则表达式匹配URL
    const match = sourceUrl.match(regex);

    const item_id = match[1];
    let productUrl = `https://mall.xiaohongshu.com/api/store/jpd/edith/detail/h5/toc?item_id=${item_id}`;
    let productVariantUrl = `https://mall.xiaohongshu.com/api/store/jpd/edith/detail/h5/toc/variant?item_id=${item_id}`;

    let productObj;
    let variantObj;
    let isError = false;

    let saveProduce = function () {
        if (productObj && variantObj) {
            let requestData = {
                product: productObj,
                productVariant: variantObj
            }
            let model = {
                Html: JSON.stringify(requestData),
                SourcePlatform: 44,
                SouceUrl: sourceUrl
            };
            SaveLiknProduct(tab, model, funCallback);
        }
    }
    request(productUrl, {
        responseType: "json"
        , method: "GET"
    }).then(data => {
        productObj = data.data;
        saveProduce();
    }).catch(reason => {
        if (!isError) {
            isError = true;
            catchFuncallback(reason, funCallback)
        }
    });
    request(productVariantUrl, {
        responseType: "json"
        , method: "GET"
    }).then(data => {
        variantObj = data.data;
        saveProduce();
    }).catch(reason => {
        if (!isError) {
            isError = true;
            catchFuncallback(reason, funCallback)
        }
    });
}

//青创网
function AnalyticalQingChuang(content, tab, sourceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    request(sourceUrl, {
        responseType: "text"
        , method: "GET"
        , headers: {
            "host": "<calculated when request is sent>"
        }
    }).then(data => {
        funCallback({ "Type": "GetQingChuangData", "HtmlStr": data }, tab, function (responseData) {

            let atrbuts = responseData.atrbuts;
            let images = responseData.images;
            let discriptions = responseData.discriptions;
            let description = responseData.description;
            let titlename = responseData.titlename;
            let voideUrl = responseData.voideUrl;
            var skus = responseData.skus;

            let mainData = {
                atrbuts: atrbuts,
                discription: description,
                discriptions,
                images: images,
                titlename: titlename,
                skus: skus,
                voideUrl: voideUrl
            }
            let mainModel = {
                Html: JSON.stringify(mainData),
                SourcePlatform: 46,
                SouceUrl: sourceUrl
            };
            //不登陆或者批量采集情况下
            SaveLiknProduct(tab, mainModel, funCallback);



        });
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
}

//西之月
function AnalyticalWestMonth(content, tab, sourceUrl, funCallback) {
    var id = sourceUrl.split('/')[4];
    if (id <= 0)
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    var postUrl = 'https://westmonth.com/shop_api/products/detail?product_id=' + id;
    funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: postUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
        if (response.IsSuccess) {
            var data = response.Data.data;
            let model = {
                Html: JSON.stringify(data),
                SourcePlatform: 47,
                SouceUrl: sourceUrl
            };
            SaveLiknProduct(tab, model, funCallback);
        }
    });
}

//抖音好货
function AnalyticalDouyinGoodStuff(content, tab, sourceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    const keepParams = ['id', 'origin_type', 'c_biz_combo', 'with_sec_did', 'h5_origin_type', 'use_link_command', 'from_link', 'entrance_info', 'utm_campaign'];
    fetch(sourceUrl)
        .then(response => response.text())
        .then(html => {
            funCallback({ "Type": "GetDouyinGoodStuff", "HtmlStr": html }, tab, function (response) {
                var model = {
                    Html: JSON.stringify(response.Data),
                    SourcePlatform: 49,
                    SouceUrl: cleanURL(sourceUrl, keepParams)
                };
                SaveLiknProduct(tab, model, funCallback);
            });
        })
        .catch(error => {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集数据错误，请检查采集URL能被正常访问!" }, tab, function (response) { });
        });
} 

//Doba
function AnalyticalDoba(content, tab, sourceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
       fetch(sourceUrl)
        .then(response => response.text())
        .then(html => {
            console.log(sourceUrl);
            console.log(html);
            funCallback({ "Type": "GetDoba", "HtmlStr": html }, tab, function (response) {
                var model = {
                    Html: JSON.stringify(response),
                    SourcePlatform: 51,
                    SouceUrl: sourceUrl
                };
                SaveLiknProduct(tab, model, funCallback);
            });
        })
        .catch(error => {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集被拦截，请刷新当前页面进行验证!" }, tab, function (response) { });
        });
}

function AnalyticalMadeInChina(content, tab, sourceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    fetch(sourceUrl)
        .then(response => response.text())
        .then(html => {
            //console.log(html);
            var model = {
                Html: btoa(encodeURI(JSON.stringify(html.replace(/\n/g, '')))),
                SourcePlatform: 54,
                SouceUrl: sourceUrl
            };
            SaveLiknProduct(tab, model, funCallback);

            // funCallback({ "Type": "GetMadeInChina", "HtmlStr": html }, tab, function (response) {
            //     var model = {
            //         Html: JSON.stringify(response),
            //         SourcePlatform: 54,
            //         SouceUrl: sourceUrl
            //     };
            //     SaveLiknProduct(tab, model, funCallback);
            // });
        })
        .catch(error => {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集被拦截，请刷新当前页面进行验证!" }, tab, function (response) { });
        });
} 

function AnalyticalMiravia(content, tab, sourceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    fetch(sourceUrl)
        .then(response => response.text())
        .then(html => { 
            funCallback({ "Type": "GetMiravia", "HtmlStr": html }, tab, function (response) {
                var model = {
                    Html: JSON.stringify(response),
                    SourcePlatform: 55,
                    SouceUrl: sourceUrl
                };
                SaveLiknProduct(tab, model, funCallback);
            });
        })
        .catch(error => {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集被拦截，请刷新当前页面进行验证!" }, tab, function (response) { });
        });
}

function cleanURL(url, keepParams) {
    try {
        const urlObj = new URL(url);
        const params = new URLSearchParams();

        // 只保留指定的参数
        for (const key of keepParams) {
            if (urlObj.searchParams.has(key)) {
                params.append(key, urlObj.searchParams.get(key));
            }
        }

        // 重新组合 URL
        const cleanUrl = urlObj.origin + urlObj.pathname + '?' + params.toString();
        return cleanUrl;
    } catch (e) {
        console.error('Invalid URL:', e);
        return url; // 如果 URL 无效，返回原值
    }
}

//包牛牛
function AnalyticalBaoNiuNiuProducts(content, tab, sourceUrl, funCallback) {
    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！"); 
    let uid = "";
    let uh = "";
    chrome.cookies.getAll({
        url: "https://www.bao66.cn",
    }, function (cookies) {
        uh = cookies.find(item => item.name === 'user_hash');
        uid = cookies.find(item => item.name === 'user_user_id');

        // let cookieArr= content.cookie.split(';');
        // for (let item of cookieArr) {
        //     if(item.indexOf('user_user_id')>-1)
        //         uid=item.split('=')[1]
        //     else if(item.indexOf('user_hash')>-1)
        //         uh=item.split('=')[1]
        // }
        let ph = content.datahash;
        let pid = content.productid;

        let productUrl = `https://www.bao66.cn/default/product/show_info?uid=${uid}&uh=${uh}&pid=${pid}&ph=${ph}`;
        let descriptionUrl = `https://www.bao66.cn/default/product/get_description?pid=${pid}&uid=${uid}&uh=${uh}&ph=${ph}`;


        funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: { "referer": sourceUrl, "cookie": content.cookie }, RequestUrl: productUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
            if (response.IsSuccess) {
                let productObj = response.Data.data;
                if (response.IsSuccess) {
                    let productData = {
                        product: productObj,
                        atrbuts: content.atrbuts,
                        images: content.images,
                        titlename: content.titlename
                    }
                    let productModel = {
                        Html: JSON.stringify(productData),
                        SourcePlatform: 45,
                        SouceUrl: sourceUrl
                    };
                    funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: { "referer": sourceUrl, "cookie": content.cookie }, RequestUrl: descriptionUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
                        if (response.IsSuccess) {
                            let descriptionObj = response.Data.data;
                            let descriptionData = {
                                product: productObj,
                                description: descriptionObj,
                                atrbuts: content.atrbuts,
                                images: content.images,
                                titlename: content.titlename
                            }
                            let descriptionModel = {
                                Html: JSON.stringify(descriptionData),
                                SourcePlatform: 45,
                                SouceUrl: sourceUrl
                            };
                            let mediaId = content.video.mediaId;
                            let path = content.video.path;
                            let cover = content.video.cover;
                            let voideUrl = `https://www.bao66.cn/ajax/product/video_play_info?mediaId=${mediaId}&path=${path}&cover=${cover}&pid=${pid}`;
                            funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: { "referer": sourceUrl, "cookie": content.cookie }, RequestUrl: voideUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
                                if (response.IsSuccess) {
                                    let requestData = {
                                        product: productObj,
                                        description: descriptionObj,
                                        atrbuts: content.atrbuts,
                                        images: content.images,
                                        titlename: content.titlename,
                                        voideUrl: response.Data.data.path_url
                                    }
                                    let model = {
                                        Html: JSON.stringify(requestData),
                                        SourcePlatform: 45,
                                        SouceUrl: sourceUrl
                                    };
                                    SaveLiknProduct(tab, model, funCallback);
                                }
                                else {
                                    SaveLiknProduct(tab, descriptionModel, funCallback);
                                }
                            });
                        } else {
                            SaveLiknProduct(tab, productModel, funCallback);
                        }
                    });
                }
            }
        });
        resolve({ 'accessToken': token ? token.value : '', 'userId': userId ? userId.value : '' });
    });
}


//包牛牛
function AnalyticalBaoNiuNiuProductsNew(content, tab, sourceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    request(sourceUrl, {
        responseType: "text"
        , method: "GET"
        , headers: {
            "host": "<calculated when request is sent>"
        }
    }).then(data => {
        funCallback({ "Type": "GetBaoNiuNiuData", "HtmlStr": data }, tab, function (responseData) {
            let atrbuts = responseData.atrbuts;
            let ph = responseData.ph;
            let pid = responseData.pid;
            let images = responseData.images;
            let discriptions = responseData.discriptions;
            let titlename = responseData.titlename;
            let cookie = responseData.cookie;
            let voideUrl = responseData.voideUrl;
            let uh = "";
            let uid = "";
            let mediaId = "";
            let path = "";
            let cover = "";
            if (voideUrl) {
                voideUrl = voideUrl.split('=')[1].replaceAll(";", "")
                let video = JSON.parse(voideUrl)
                if (video) {
                    mediaId = video.mediaId;
                    path = video.path;
                    cover = video.cover;
                }
            }
            if (cookie && cookie.indexOf("user_user_id") > -1) {
                let cookieArr = cookie.split(';');
                for (let item of cookieArr) {
                    if (item.indexOf("user_user_id") > -1)
                        uid = item.split('=')[1];
                    if (item.indexOf("user_hash") > -1)
                        uh = item.split('=')[1];
                }
                let productUrl = `https://www.bao66.cn/default/product/show_info?uid=${uid}&uh=${uh}&pid=${pid}&ph=${ph}`;
                let descriptionUrl = `https://www.bao66.cn/default/product/get_description?pid=${pid}&uid=${uid}&uh=${uh}&ph=${ph}`;
                //获取变体图
                funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: { "referer": sourceUrl, "cookie": cookie }, RequestUrl: productUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
                    if (response.IsSuccess) {
                        let productObj = response.Data.data;
                        if (response.IsSuccess) {
                            let productData = {
                                product: productObj,
                                atrbuts: atrbuts,
                                images: images,
                                titlename: titlename,
                                discriptions: discriptions
                            }
                            let productModel = {
                                Html: JSON.stringify(productData),
                                SourcePlatform: 45,
                                SouceUrl: sourceUrl
                            };
                            funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: { "referer": sourceUrl, "cookie": cookie }, RequestUrl: descriptionUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
                                if (response.IsSuccess) {
                                    let descriptionObj = response.Data.data;
                                    let descriptionData = {
                                        product: productObj,
                                        description: descriptionObj,
                                        atrbuts: atrbuts,
                                        images: images,
                                        titlename: titlename,
                                        discriptions: discriptions
                                    }
                                    let descriptionModel = {
                                        Html: JSON.stringify(descriptionData),
                                        SourcePlatform: 45,
                                        SouceUrl: sourceUrl
                                    };
                                    if (path && cover) {
                                        var voideUrls = `https://www.bao66.cn/ajax/product/video_play_info?mediaId=${mediaId}&path=${path}&cover=${cover}&pid=${pid}`;
                                        funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: { "referer": sourceUrl, "cookie": cookie }, RequestUrl: voideUrls, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
                                            if (response.IsSuccess) {
                                                let lastData = {
                                                    product: productObj,
                                                    description: descriptionObj,
                                                    atrbuts: atrbuts,
                                                    images: images,
                                                    titlename: titlename,
                                                    voideUrl: response.Data.data.path_url,
                                                    discriptions: discriptions
                                                }
                                                let lastModel = {
                                                    Html: JSON.stringify(lastData),
                                                    SourcePlatform: 45,
                                                    SouceUrl: sourceUrl
                                                };
                                                //获取视频成功
                                                SaveLiknProduct(tab, lastModel, funCallback);
                                            } else {
                                                //获取视频失败
                                                SaveLiknProduct(tab, descriptionModel, funCallback);
                                            }

                                        });
                                    } else {
                                        //获取视频失败
                                        SaveLiknProduct(tab, descriptionModel, funCallback);
                                    }
                                } else {
                                    //获取描述失败
                                    SaveLiknProduct(tab, productModel, funCallback);
                                }
                            });
                        }
                    }
                    else {
                        let mainData = {
                            atrbuts: atrbuts,
                            images: images,
                            titlename: titlename,
                            discriptions: discriptions
                        }
                        let mainModel = {
                            Html: JSON.stringify(mainData),
                            SourcePlatform: 45,
                            SouceUrl: sourceUrl
                        };
                        //获取变体失败
                        SaveLiknProduct(tab, mainModel, funCallback);
                    }
                });
            } else {
                let mainData = {
                    atrbuts: atrbuts,
                    images: images,
                    titlename: titlename
                }
                let mainModel = {
                    Html: JSON.stringify(mainData),
                    SourcePlatform: 45,
                    SouceUrl: sourceUrl
                };
                //不登陆或者批量采集情况下
                SaveLiknProduct(tab, mainModel, funCallback);
            }
        });
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
}

//包牛牛
function AnalyticalBaoNiuNiuProducts(content, tab, sourceUrl, funCallback) {
    if (content === "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
    let uid = "";
    let uh = "";
    chrome.cookies.getAll({
        url: "https://www.bao66.cn",
    }, function (cookies) {
        uh = cookies.find(item => item.name === 'user_hash');
        uid = cookies.find(item => item.name === 'user_user_id');

        // let cookieArr= content.cookie.split(';');
        // for (let item of cookieArr) {
        //     if(item.indexOf('user_user_id')>-1)
        //         uid=item.split('=')[1]
        //     else if(item.indexOf('user_hash')>-1)
        //         uh=item.split('=')[1]
        // }
        let ph = content.datahash;
        let pid = content.productid;

        let productUrl = `https://www.bao66.cn/default/product/show_info?uid=${uid}&uh=${uh}&pid=${pid}&ph=${ph}`;
        let descriptionUrl = `https://www.bao66.cn/default/product/get_description?pid=${pid}&uid=${uid}&uh=${uh}&ph=${ph}`;


        funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: { "referer": sourceUrl, "cookie": content.cookie }, RequestUrl: productUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
            if (response.IsSuccess) {
                let productObj = response.Data.data;
                if (response.IsSuccess) {
                    let productData = {
                        product: productObj,
                        atrbuts: content.atrbuts,
                        images: content.images,
                        titlename: content.titlename
                    }
                    let productModel = {
                        Html: JSON.stringify(productData),
                        SourcePlatform: 45,
                        SouceUrl: sourceUrl
                    };
                    funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: { "referer": sourceUrl, "cookie": content.cookie }, RequestUrl: descriptionUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
                        if (response.IsSuccess) {
                            let descriptionObj = response.Data.data;
                            let descriptionData = {
                                product: productObj,
                                description: descriptionObj,
                                atrbuts: content.atrbuts,
                                images: content.images,
                                titlename: content.titlename
                            }
                            let descriptionModel = {
                                Html: JSON.stringify(descriptionData),
                                SourcePlatform: 45,
                                SouceUrl: sourceUrl
                            };
                            let mediaId = content.video.mediaId;
                            let path = content.video.path;
                            let cover = content.video.cover;
                            let voideUrl = `https://www.bao66.cn/ajax/product/video_play_info?mediaId=${mediaId}&path=${path}&cover=${cover}&pid=${pid}`;
                            funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: { "referer": sourceUrl, "cookie": content.cookie }, RequestUrl: voideUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
                                if (response.IsSuccess) {
                                    let requestData = {
                                        product: productObj,
                                        description: descriptionObj,
                                        atrbuts: content.atrbuts,
                                        images: content.images,
                                        titlename: content.titlename,
                                        voideUrl: response.Data.data.path_url
                                    }
                                    let model = {
                                        Html: JSON.stringify(requestData),
                                        SourcePlatform: 45,
                                        SouceUrl: sourceUrl
                                    };
                                    SaveLiknProduct(tab, model, funCallback);
                                }
                                else {
                                    SaveLiknProduct(tab, descriptionModel, funCallback);
                                }
                            });
                        } else {
                            SaveLiknProduct(tab, productModel, funCallback);
                        }
                    });
                }
            }
        });
        resolve({ 'accessToken': token ? token.value : '', 'userId': userId ? userId.value : '' });
    });
}

function AnalyticalWildberriesProducts(content, tab, souceUrl, funCallback) {
    const urlObj = new URL(souceUrl);
    const wbDomain = urlObj.hostname;

    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    //组装域名
    function volHostV2(e) {
        let t;
        switch (!0) {
            case e >= 0 && e <= 143:
                t = "01";
                break;
            case e <= 287:
                t = "02";
                break;
            case e <= 431:
                t = "03";
                break;
            case e <= 719:
                t = "04";
                break;
            case e <= 1007:
                t = "05";
                break;
            case e <= 1061:
                t = "06";
                break;
            case e <= 1115:
                t = "07";
                break;
            case e <= 1169:
                t = "08";
                break;
            case e <= 1313:
                t = "09";
                break;
            case e <= 1601:
                t = "10";
                break;
            case e <= 1655:
                t = "11";
                break;
            case e <= 1919:
                t = "12";
                break;
            case e <= 2045:
                t = "13";
                break;
            case e <= 2189:
                t = "14";
                break;
            case e <= 2405:
                t = "15";
                break;
            case e <= 2621:
                t = "16";
                break;
            case e <= 2837:
                t = "17";
                break;
            case e <= 3053:
                t = "18";
                break;
            case e <= 3269:
                t = "19";
                break;
            case e <= 3485:
                t = "20";
                break;
            case e <= 3701:
                t = "21";
                break;
            case e <= 3917:
                t = "22";
                break;
            case e <= 4133:
                t = "23";
                break;
            case e <= 4349:
                t = "24";
                break;
            case e <= 4565:
                t = "25";
                break;
            case e <= 4877:
                t = "26";
                break;
            case e <= 5189:
                t = "27";
                break;
            case e <= 5501:
                t = "28";
                break;
            case e <= 5813:
                t = "29";
                break;
            case e <= 6125:
                t = "30";
                break;
            case e <= 6437:
                t = "31";
                break;
            case e <= 6749:
                t = "32";
                break;
            case e <= 7061:
                t = "33";
                break;
            case e <= 7373:
                t = "34";
                break;
            case e <= 7685:
                t = "35";
                break;
            case e <= 7997:
                t = "36";
                break;
            case e <= 8309:
                t = "37";
                break;
            case e <= 8741:
                t = "38"
                break;
            case e <= 9173:
                t = "39"
                break;
            case e <= 9605:
                t = "40"
                break;
            case e <= 10373:
                t = "41"
                break;
            case e <= 11141:
                t = "42"
                break;
            case e <= 11909:
                t = "43"
                break;
            case e <= 12677:
                t = "44"
                break;
            case e <= 13445:
                t = "45"
                break;
            case e <= 14213:
                t = "46"
                break;
            default:
                t = "47"
        }
        return `basket-${t}.wbbasket.ru`;
    }
    //组装域名
    function volVideoHost(e) {
        let t;
        switch (!0) {
            case e >= 0 && e <= 11:
                t = "01";
                break;
            case e <= 23:
                t = "02";
                break;
            case e <= 35:
                t = "03";
                break;
            case e <= 47:
                t = "04";
                break;
            case e <= 59:
                t = "05";
                break;
            case e <= 71:
                t = "06";
                break;
            case e <= 83:
                t = "07";
                break;
            case e <= 95:
                t = "08";
                break;
            case e <= 107:
                t = "09";
                break;
            case e <= 119:
                t = "10";
                break;
            case e <= 131:
                t = "11";
                break;
            case e <= 143:
                t = "12";
                break;
            default:
                t = "13"
        }
        return `tvideobasket-${t}.wbbasket.ru`
    }

    //组装请求路径
    function constructHostV2(e, t = "nm") {
        const r = parseInt(e, 10)
            , n = "video" === t ? r % 144 : ~~(r / 1e5)
            , a = "video" === t ? ~~(r / 1e4) : ~~(r / 1e3);
        let o;
        return "nm" === t ? o = volHostV2(n) : "video" === t && (o = volVideoHost(n)),
            `https://${o}/vol${n}/part${a}/${r}`;
    }

    const regex = /\/catalog\/(\d+)\//;
    const match = souceUrl.match(regex);

    let skc = match ? match[1] : null;

    if (!skc) {
        const queryString = souceUrl.split('?')[0];
        if (queryString) {
            const urlArray = queryString.split('/');
            const lastUrlPart = urlArray[urlArray.length - 1];
            const skcMatch = lastUrlPart.match(/(\d+)(?:\D*)$/);
            skc = skcMatch ? skcMatch[1] : null;
        }
    }

    if (!skc) {
        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "\u672a\u83b7\u53d6\u5230\u4ea7\u54c1\u6570\u636e\uff0c\u8bf7\u5728\u4ea7\u54c1\u8be6\u60c5\u9875\u91c7\u96c6\u8bd5\u8bd5" }, tab, function (response) { });
        return;
    }

    var jsonData = {};
    if (content?.videoUrl) {
        jsonData.videoUrl = content.videoUrl;
    }

    function sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function distinctList(list) {
        return list.filter((item, index) => item && list.indexOf(item) === index);
    }

    function hasProducts(data) {
        return data && Array.isArray(data.products) && data.products.length > 0;
    }

    function fetchJsonWithRetry(url, options, retryCount) {
        retryCount = retryCount == null ? 2 : retryCount;
        return new Promise((resolve, reject) => {
            var lastError = null;
            var attemptFetch = function (index) {
                fetch(url, options)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Network response was not ok (' + response.status + ')');
                        }
                        return response.json();
                    })
                    .then(resolve)
                    .catch(error => {
                        lastError = error;
                        if (index < retryCount) {
                            sleep(300 + index * 500).then(() => attemptFetch(index + 1));
                        } else {
                            reject(lastError);
                        }
                    });
            };
            attemptFetch(0);
        });
    }

    function fetchFirstJson(urls, options, validate) {
        var lastError = null;
        var index = 0;
        var next = function () {
            if (index >= urls.length) {
                return Promise.reject(lastError || new Error('All requests failed'));
            }
            var currentUrl = urls[index++];
            return fetchJsonWithRetry(currentUrl, options, 2)
                .then(data => {
                    if (validate && !validate(data)) {
                        throw new Error('Response data is empty');
                    }
                    return data;
                })
                .catch(error => {
                    lastError = error;
                    return next();
                });
        };
        return next();
    }

    var baseUrl = constructHostV2(skc);
    var spuUrls = distinctList([
        baseUrl + '/info/ru/card.json',
        baseUrl + '/info/card.json'
    ]);

    fetchFirstJson(spuUrls, {}, data => data != null && data.colors != null && data.colors != '' && data.colors != undefined)
        .then(data => {
            jsonData.spuData = data;

            var nmList = Array.isArray(data.colors) ? data.colors : [data.colors];
            nmList = nmList.map(x => x + '').filter(x => x);
            if (nmList.length === 0) {
                throw new Error('Response colors is empty');
            }

            var nm = nmList.join(';');
            var skcUrls = distinctList([
                'https://' + wbDomain + '/__internal/u-card/cards/v4/detail?appType=1&curr=rub&dest=-1257786&nm=' + nm,
                'https://' + wbDomain + '/__internal/u-card/cards/v4/detail?appType=1&curr=rub&dest=-1257786&lang=ru&nm=' + nm,
                'https://www.wildberries.ru/__internal/u-card/cards/v4/detail?appType=1&curr=rub&dest=-1257786&nm=' + nm,
                'https://card.wb.ru/cards/v4/detail?appType=1&curr=rub&dest=-1257786&nm=' + nm,
                'https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&nm=' + nm
            ]);

            return fetchFirstJson(skcUrls, {
                method: 'GET',
                mode: 'cors',
                headers: {
                    'deviceid': 'site_14bac2fca53c495cb242f71ee2d2c1a5'
                }
            }, hasProducts);
        })
        .then(skcData => {
            jsonData.skcData = skcData;
            var model = {
                //Html: btoa(encodeURI(JSON.stringify(jsonData))),
                SourcePlatform: 35,
                SouceUrl: souceUrl,
                MoreData: JSON.stringify(jsonData)
            };
            SaveLiknProduct(tab, model, funCallback);
        })
        .catch(error => {
            console.warn('Wildberries collect failed:', error);
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "未获取到产品SKC数据，请在产品详情页采集试试" }, tab, function (response) { });
        });
    return;
}

function AnalyticalSaleyeeProducts(content, tab, souceUrl, funCallback) {
    var imageList = [];
    var title = '';
    var desc = '';
    var propertyNames = [];
    var categoryId = 0;
    var Parameters = [];
    var categoryName = '';
    var variations = [];
    var notificationKey = new Date().getTime();
    const parsedUrl = new URL(souceUrl);
    const domain = parsedUrl.origin;
    let width2 = 0;
    let weight2 = 0;
    let height2 = 0;
    let length2 = 0;
    var saveProductData = function () {
        var box =
        {
            "Title": title,
            "DetailedDescription": btoa(encodeURI(desc)),
            "BriefDescription": convertHtmlToPlainText(desc),
            "ImageUrl": imageList.join("|"),
            "PropertyName": propertyNames.length > 0 ? JSON.stringify(propertyNames) : "[]",
            "PlatformCategoryId": categoryId,
            "SourceUrl": souceUrl,
            "VideoUrl": '',
            "IsClaimed": false,
            "SourcePlatform": 41,
            "Tags": [],
            "Remark": "",
            "CreateTime": "1900-01-01 00:00:00",
            "Parameters": JSON.stringify(Parameters),
            "PlatformCategoryName": categoryName,
            "Width2": width2,
            "Weight2": weight2,
            "Height2": height2,
            "Length2": length2
        };
        if (variations.length > 0) {
            variations.forEach((item) => {
                if (item.Property != null && item.Property.length > 0) {
                    item.Property = JSON.stringify(item.Property.map(x => {
                        return { "Key": x.key, "Value": x.value }
                    }))
                }
            })
        }
        funCallback({ "Type": "NotificationClose", "Key": notificationKey }, tab, () => { });
        SaveProduct(tab, { "Box": box, "BoxItem": variations }, funCallback);
    }
    var getCategoryId = function (url) {
        //获取类目id
        request(`${url}`, { responseType: "text", method: "GET" }).then((res) => {
            funCallback({ "Type": "GetSaleyeeCategory", "HtmlStr": res }, tab, function (response) {
                categoryId = response.id;
                saveProductData();
            })
        })
    }
    var getDescText = function (pid) {
        request(`${domain}/Product/GetProductDescription?pid=${pid}`, { responseType: "text", method: "GET" }).then(res => {
            funCallback({ "Type": "GetSaleyeeDesc", "HtmlStr": desc, "desc": res }, tab, function (response) {
                desc = response.desc;
            })
        })
    }

    var getvariationsInfo = function (skuid, spucode) {
        return new Promise(resolve => {
            const form = new FormData();
            form.append("platformGoodsCode", skuid);
            form.append("spu", spucode);
            const options = {
                method: 'POST',
                headers: {
                    Accept: '*/*',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'User-Agent': 'PostmanRuntime-ApipostRuntime/1.1.0',
                    Connection: 'keep-alive'
                },
                body: form
            };
            request(`${domain}/Product/ProductDetailsSwitchLoadAsync`, options
            ).then(res => {
                if (res.Flag == 1) {
                    var skuAttr = res.SkuModel.Attribute_String.split("，").map(pair => {
                        const [key, value] = pair.split("：");
                        return { key: key.trim(), value: value.trim() };
                    });
                    var skuImages = res.SkuModel.PictureModels.map(x => x.ImageUrl);
                    skuImages.forEach((image) => {
                        if (!imageList.includes(image)) {
                            imageList.push(image);
                        }
                    })
                    var skuid = res.SkuModel.PlatformGoodsCode;
                    var stockNum = 0;
                    var price = 0;
                    if (res.SkuModel.ProductDetailRegionLogisticsProductList && res.SkuModel.ProductDetailRegionLogisticsProductList.length > 0) {
                        stockNum = res.SkuModel.ProductDetailRegionLogisticsProductList[0].StockQty
                        var product = res.SkuModel.ProductDetailRegionLogisticsProductList[0].ProductDetailLogisticsProductList;
                        if (product && product.length > 0) {
                            price = product[0].Price_d;
                        }
                    }
                    variations.forEach((item) => {
                        var isUpdate = compareArraysByKeyAndValue(item.Property, skuAttr);
                        if (isUpdate) {
                            item.VariantImageUrl = skuImages[0];
                            item.Price = price;
                            return;
                        }
                    })
                    resolve();
                }

            }).catch(reason => {
                console.log(reason);
                resolve();
            });
        });
    }

    function compareArraysByKeyAndValue(arr1, arr2) {
        if (arr1.length !== arr2.length) return false;

        // 按 key 排序两个数组
        const sortedArr1 = arr1.slice().sort((a, b) => a.key.localeCompare(b.key));
        const sortedArr2 = arr2.slice().sort((a, b) => a.key.localeCompare(b.key));

        // 检查排序后的每个对象的 key 和 value 
        return sortedArr1.every((item, index) =>
            item.key === sortedArr2[index].key && item.value === sortedArr2[index].value
        );
    }
    request(souceUrl, { responseType: "text", method: "GET" }).then((res) => {
        funCallback({ "Type": "GetSaleyeeProductInfo", "HtmlStr": res }, tab, function (response) {
            //请求sku的价格，图片
            if (response) {
                desc = response.Desc;
                propertyNames = response.PropertyNames;
                categoryName = response.CategoryName;
                Parameters = response.Parameters;
                imageList = response.ImageList
                title = response.Title;
                width2 = response.width2;
                length2 = response.length2;
                height2 = response.height2;
                weight2 = response.weight2;
                variations = response.Skus;
                getDescText(response.productId);
                if (response.CategoryId.indexOf(domain) == -1) {
                    response.CategoryId = domain + response.CategoryId
                }
                if (response.allProductIds.length > 1) {
                    var tasks = []
                    for (i = 0; i < response.allProductIds.length; i++) {
                        tasks.push(getvariationsInfo(response.allProductIds[i], response.SpuCode));
                    }
                    Promise.all(tasks).then(result => {
                        getCategoryId(response.CategoryId);
                    }).catch(error => {
                        funCallback({ "Type": "NotificationClose", "Key": notificationKey }, tab, () => { });
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Fruugo产品解析失败！" + error.message }, tab, function (response) { });
                        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
                    });
                } else {
                    getCategoryId(response.CategoryId);
                }
            } else {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "获取产品失败！" }, tab, function (response) { });
            }
        });
    });

}

function AnalyticalFruugoroducts(content, tab, souceUrl, funCallback) {
    var productInfo = extractTitleAndProductId(souceUrl);
    var imageList = [];
    var title = '';
    var desc = '';
    var propertyNames = [];
    var categoryId = 0;
    var Parameters = [];
    var categoryName = '';
    var variations = [];
    var notificationKey = new Date().getTime();
    const parsedUrl = new URL(souceUrl);
    const domain = parsedUrl.origin;

    //处理变体数据请求链接
    var normalizeFruugoUrl = function (url) {
        // 分成两部分：标题部分 + p-xxxxxxxxx 这段
        const match = url.match(/^(https:\/\/www\.fruugo\.co\.uk\/)(.+)(\/p-\d+-\d+)$/i);
        if (!match) return url; // 格式不符则原样返回

        let prefix = match[1];
        let title = match[2];
        let suffix = match[3];

        // &amp; 变成 &
        title = title.replace(/&amp;/g, "&");

        // 转小写
        title = title.toLowerCase();

        // 把空格、逗号、| 等全部转成 -
        title = title.replace(/[^a-z0-9]+/g, "-");

        // 去掉开头和结尾的 -
        title = title.replace(/^-+|-+$/g, "");

        return prefix + title + suffix;
    }

    var saveProductData = function () {
        var box =
        {
            "Title": title,
            "DetailedDescription": btoa(encodeURI(desc)),
            "BriefDescription": convertHtmlToPlainText(desc),
            "ImageUrl": imageList.join("|"),
            "PropertyName": propertyNames.length > 0 ? JSON.stringify(propertyNames) : "[]",
            "PlatformCategoryId": categoryId,
            "SourceUrl": souceUrl,
            "VideoUrl": '',
            "IsClaimed": false,
            "SourcePlatform": 39,
            "Tags": [],
            "Remark": "",
            "CreateTime": "1900-01-01 00:00:00",
            "Parameters": JSON.stringify(Parameters),
            "PlatformCategoryName": categoryName
        };
        funCallback({ "Type": "NotificationClose", "Key": notificationKey }, tab, () => { });
        console.log(box, variations);
        SaveProduct(tab, { "Box": box, "BoxItem": variations }, funCallback);
    }
    var getvariationsInfo = function (skuid, index) {
        return new Promise(resolve => {
            let requestUrl = `${domain}/${title}/p-${productInfo.productId}-${skuid}`;
            requestUrl = normalizeFruugoUrl(requestUrl);
            //console.log("requestUrl", requestUrl);
            request(requestUrl, {
                responseType: "text"
                , method: "GET"
            }).then(res => {
                funCallback({ "Type": "GetFruugoVariationsInfo", "HtmlStr": res }, tab, function (skuRes) {
                    variations[index].Price = skuRes.Price;
                    variations[index].Currency = skuRes.Currency;
                    variations[index].VariantImageUrl = skuRes.ImageList[0];
                    variations[index].Property = JSON.stringify(skuRes.SkuAttr);
                    //判断图片是否已经存在
                    let skuImage = skuRes.ImageList;
                    // 遍历 skuImage 数组，将不在 ImageList 中的元素添加到 ImageList 中
                    skuImage.forEach((image) => {
                        if (!imageList.includes(image)) {
                            imageList.push(image);
                        }
                    });
                    resolve();
                });
            }).catch(reason => {
                console.log(reason);
                resolve();
            });
        });
    }
    if (productInfo.productId === 0) {
        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "获取产品id失败！" }, tab, function (response) { });
    }
    request(souceUrl, { responseType: "text", method: "GET" }).then((res) => {
        funCallback({ "Type": "GetFruugoProductInfo", "HtmlStr": res }, tab, function (response) {
            //请求sku的价格，图片
            if (response) {
                desc = response.Desc;
                propertyNames = response.PropertyNames;
                categoryId = response.CategoryId;
                categoryName = response.CategoryName;
                Parameters = response.Parameters;
                imageList = response.ImageList
                title = response.Title;
                if (response.HasMoreSku) {

                    variations.push({
                        Price: response.Price,
                        Property: JSON.stringify(response.SkuAttr),
                        Currency: response.Currency,
                        VariantImageUrl: imageList[0],
                    })
                    var tasks = []
                    for (i = 0; i < response.OtherSkuids.length; i++) {
                        variations.push({
                            Price: 0,
                            Property: [],
                            Currency: '',
                            VariantImageUrl: '',
                        });
                        tasks.push(getvariationsInfo(response.OtherSkuids[i], i + 1));
                    }
                    Promise.all(tasks).then(result => {
                        saveProductData();
                    }).catch(error => {
                        funCallback({ "Type": "NotificationClose", "Key": notificationKey }, tab, () => { });
                        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Fruugo产品解析失败！" + error.message }, tab, function (response) { });
                        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");
                    });
                } else {
                    //单属性 
                    variations = [{
                        Price: response.Price,
                        Property: "[]",
                        Currency: response.Currency,
                        VariantImageUrl: response.ImageList[0],
                    }];
                    saveProductData();
                }
            } else {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "获取产品id失败！" }, tab, function (response) { });
            }
        });
    });

    function extractTitleAndProductId(url) {
        const titlePattern = /\/([^\/]+)\/p-(\d+)(?:-\d+)?/;
        const match = url.match(titlePattern);

        if (match) {
            return {
                title: match[1].replace(/-/g, " "),
                productId: match[2],
            };
        } else {
            return { title: "", productId: 0 };
        }
    }
}

function AnalyticalSheinProducts(content, tab, souceUrl, funCallback) {
    function findJsonEnd(content, startIndex) {
        let braceCount = 0;
        for (let i = startIndex; i < content.length; i++) {
            if (content[i] === '{') braceCount++;
            if (content[i] === '}') braceCount--;
            if (braceCount === 0) return i;
        }
        return -1;
    }

    //截取来源地址的请求地址
    function extractDomain(url) {
        const regex = /^(https:\/\/[^\/]+)\//;
        const match = url.match(regex);
        if (match) {
            return match[1];
        } else {
            return null;
        }
    }

    //请求被拦截处理
    function requestInterceptionProcessing() {
        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "Shein采集被拦截！请更换网络代理节点刷新页面或稍后重试！" }, tab, function (response) { });
        funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
    }

    fetch(souceUrl)
        .then(response => response.text())
        .then(html => {
            console.log("sheinHTML", html);
            let jsonStr = "";
            const scriptStartTag = '<script>';
            const scriptEndTag = '</script>';

            let index = 0;
            //截取页面json数据
            while (true) {
                const start = html.indexOf(scriptStartTag, index);
                if (start === -1) break;

                const end = html.indexOf(scriptEndTag, start);
                if (end === -1) break;

                const scriptContent = html.substring(start + scriptStartTag.length, end).trim();
                const startIndex = scriptContent.indexOf('window.gbRawData =');
                if (startIndex !== -1) {
                    // 找到 window.gbRawData 的起始位置
                    const jsonStart = scriptContent.indexOf('{', startIndex + 'window.gbRawData ='.length);
                    const jsonEnd = findJsonEnd(scriptContent, jsonStart);
                    if (jsonStart !== -1 && jsonEnd !== -1) {
                        // 提取 JSON 数据
                        jsonStr = scriptContent.substring(jsonStart, jsonEnd + 1);
                        break;
                    }
                }
                index = end + scriptEndTag.length;
            }

            if (jsonStr == null || jsonStr == "") {
                requestInterceptionProcessing();
                return;
            }

            funCallback({ "Type": "GetSheinPagePrice", "HtmlStr": html }, tab, function (response) {
                let collectJsonData = {
                    productData: jsonStr,
                    pagePrice: response.price,
                }
                var model = {
                    Html: btoa(encodeURI(JSON.stringify(collectJsonData))),
                    SourcePlatform: 38,
                    SouceUrl: souceUrl
                };
                SaveLiknProduct(tab, model, funCallback);
            });

        })
        .catch(error => {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集数据错误，请检查采集URL能被正常访问!" }, tab, function (response) { });
        });
}

function AnalyticalTiktokProducts(content, tab, souceUrl, funCallback) {

    //plan C
    funCallback({ Type: "GetAjaxResult", RequestMethod: "POST", RequestHeaders: {}, RequestUrl: souceUrl, RequestDataType: "html", RequestData: "" }, tab, function (response) {
        if (response.IsSuccess) {
            funCallback({ "Type": "GetTiktokData", "HtmlStr": response.Data }, tab, function (pageResponse) {
                var model = {
                    Html: btoa(encodeURI(JSON.stringify(response.Data))),
                    SourcePlatform: 32,
                    SouceUrl: souceUrl,
                    MoreData: JSON.stringify(pageResponse.data)
                };
                SaveLiknProduct(tab, model, funCallback);
            });
        } else {
            throw new Error("未能成功获取到产品数据，请刷新页面后重试");
        }
    });

    //plan B    
    //如有local、region参数可使用路径获取json
    // if((souceUrl.indexOf("local") >= 0 && souceUrl.indexOf("region") >= 0) || souceUrl.indexOf("shop-sg.tiktok.com") >= 0){

    // getRedirectedUrl(souceUrl).then(finalUrl => {
    //     // 创建一个URL对象
    //     const url = new URL(finalUrl);

    //     // 定义需要保留的查询参数
    //     const allowedParams = ['region', 'locale', 'local'];

    //     // 过滤查询参数
    //     for (const key of [...url.searchParams.keys()]) {
    //         if (!allowedParams.includes(key)) {
    //             url.searchParams.delete(key); // 删除不需要的参数
    //         }
    //     }

    //     //let requestUrl = url.toString() + "&__loader=%28shop%24%29%2F%28pdp%29%2F%28name%24%29%2F%28id%29%2Fpage&__ssrDirect=true";
    //     url.searchParams.set("__loader", "(shop$)/(pdp)/(name$)/(id)/page");
    //     url.searchParams.set("__ssrDirect", "true");
    //     let requestUrl = url.toString();

    //     funCallback({ Type: "GetAjaxResult", RequestMethod: "GET", RequestHeaders: {}, RequestUrl: requestUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: {}, }, tab, function (response) {
    //             if (response.IsSuccess) {
    //                 let data = response.Data;
    //                 let data2 = response.Data.initialData.productInfo;
    //                 let model = {
    //                     Html: "",
    //                     SourcePlatform: 32,
    //                     SouceUrl: souceUrl,
    //                     MoreData: JSON.stringify(response.Data.initialData.productInfo)
    //                 };
    //                 SaveLiknProduct(tab, model, funCallback);
    //             }
    //             else {
    //                 SaveLiknProduct(tab, model, funCallback);
    //             }
    //         });
    //     });
    // }

    //plan A
    // else{
    //     getRedirectedUrl(souceUrl).then(finalUrl => {
    //         fetch(finalUrl)
    //         .then(response => response.text())
    //         .then(html => {
    //             funCallback({ "Type": "GetTiktokData", "HtmlStr": html }, tab, function (response) {
    //                 var model = {
    //                     Html: btoa(encodeURI(JSON.stringify(html))),
    //                     SourcePlatform: 32,
    //                     SouceUrl: souceUrl,
    //                     MoreData:JSON.stringify(response.data)
    //                 };
    //                 SaveLiknProduct(tab, model, funCallback);
    //             });
    //         })
    //         .catch(error => {
    //             funCallback({ "Type": "Alter", "MessageType": "error", "Message": "采集数据错误，请检查采集URL能被正常访问!"}, tab, function (response) { });
    //         });
    //     });
    // }

}

//获取重定向后的URL
function getRedirectedUrl(url) {
    return fetch(url, {
        method: 'GET', // GET 请求来获取完整的内容
        redirect: 'follow' // 自动跟随重定向
    })
        .then(response => {
            // 返回最终的 URL，无论是否发生重定向
            const finalUrl = response.url;
            console.log('Final URL (Redirected or Original):', finalUrl);
            return finalUrl; // 返回最终的 URL
        })
        .catch(error => {
            console.error('Error:', error);
            return url; // 如果请求失败，返回 null
        });
}

function AnalyticalCategory(platformId, content, tab, funCallback) {

    switch (platformId) {
        case 5:
            try {
                ALiBaBaCategoryCollect(content, tab, funCallback);
            } catch (error) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "类目采集失败!" + error.message }, tab, function (response) { });
                funCallback({ "Type": "CheckCategoryBtnDisabled", "Disabled": false }, tab, function (response) { });
            }
            break;
    }
}

//1688类目采集
let totalCount = 0;//总产品数量
var CATEGORY_SAVE_LIMIT_MESSAGE = '添加失败，采集箱数量保存上限100万行，请删除已认领或过期数据。';
function ALiBaBaCategoryCollect(contend, tab, funCallback) {
    var url = contend.url;
    var documentCatId = contend.catid;
    var pageNum = contend.pageNum;
    var h5_tk = contend.token;
    request(url, {
        responseType: "TEXT"
        , method: "GET"
    }).then(data => {
        var timeStr = new Date().getTime(),
            memberId = '',
            catId = '',
            catPid = '',
            urlId = url.split('?')[0];

        var memberArr = data.split('sellerMemberId=');
        if (memberArr.length > 1) {
            memberId = memberArr[1];
            memberId = memberId.substring(0, memberId.indexOf('&'))
        }

        if (urlId) {
            var idArr = urlId.split('_');
            if (idArr.length === 2) {
                catId = idArr[1].split('.')[0];
            }
            if (idArr.length === 3) {
                catId = idArr[1];
                catPid = idArr[2].split('.')[0];
            }
        }
        catId = void 0 === catId ? "" : catId;
        var dataStr = JSON.stringify({
            dataType: "moduleData",
            argString: JSON.stringify({
                appName: "pcmodules",
                appdata: {
                    catId: documentCatId ? documentCatId : catId,
                    count: 30,
                    mixFilter: !1,
                    pageNum: pageNum,
                    quantityBegin: null,
                    sellerRecommendFilter: !1,
                    sortType: "wangpu_score",
                    tradenumFilter: !1
                },
                memberId: memberId,
                resourceName: "wpOfferColumn",
                type: "view",
                version: "1.0.0"
            })
        });
        //var postData = "data=" + dataStr
        var sign = getAlibabaCategorySign(h5_tk.split("_")[0], timeStr, dataStr);

        var postUrl = 'https://h5api.m.1688.com/h5/mtop.1688.shop.data.get/1.0/?jsv=2.7.0&appKey=12574478&t=' + timeStr +
            '&sign=' + sign + '&api=mtop.1688.shop.data.get&v=1.0&type=json&valueType=string&dataType=json&timeout=10000';


        let categoryPageSize = 30;//每页最大产品数量

        //每次请求间隔300ms
        setTimeout(() => {
            funCallback({ Type: "GetAjaxResult", RequestMethod: "POST", RequestHeaders: {}, RequestUrl: postUrl, RequestContentType: "application/x-www-form-urlencoded; charset=UTF-8", RequestDataType: "json", RequestData: { "data": dataStr }, }, tab, function (response) {
                if (response.IsSuccess) {
                    if (response.Data?.data?.content?.offerList?.length > 0) {
                        var list = [];
                        var offerList = response.Data.data.content.offerList;

                        totalCount = Number(response.Data.data.content.offerCount);
                        for (var i = 0; i < offerList.length; i++) {
                            list.push('https://detail.1688.com/offer/' + offerList[i].id + '.html');
                        }
                        funCallback({ "Type": "AlibabaCategoryCrawl", "pageNum": pageNum, "data": list, "totalCount": totalCount }, tab, function (response) {
                            AliBaBacallNextPage(response, tab, funCallback)
                        });
                    } else {
                        //2026-05-25用户反馈按店铺采集阻塞，不知是否是offerList没有数据，在此处加上调试代码，pageNum：页码
                        console.log(`未获取到1688产品链接数据，pageNum：${pageNum}，接口数据：`, response.Data);

                        if (response.Data?.data?.content?.offerCount > 0)
                            totalCount = Number(response.Data.data.content.offerCount);

                        var maxPageNum = totalCount > 0 ? Math.ceil(totalCount / categoryPageSize) : 0;
                        var isLastPage = maxPageNum > 0 && pageNum >= maxPageNum;
                        //无返回数据：非末页+30，末页补齐剩余数量，进度与失败数同步增加
                        funCallback({
                            "Type": "SetCategoryProgress",
                            "ProcessType": 3,
                            "Count": categoryPageSize,
                            "FillToTotal": isLastPage
                        }, tab, function (response) {
                            funCallback({ "Type": "AlibabaCategoryCrawl", "pageNum": pageNum, "data": [], "totalCount": totalCount }, tab, function (response) {
                                if (pageNum < maxPageNum && response.next && response.next != '')
                                    ALiBaBaCategoryCollect(response, tab, funCallback);
                                else
                                    funCallback({ "Type": "SetCategoryResult" }, tab, function (response) { });
                            });
                        });
                    }
                } else {
                    CategroyErrorCall("采集失败！若此错误频繁出现，请联系客服！", tab, funCallback);
                }
            });
        }, 300);

    }).catch(reason => {
        CategroyErrorCall("采集失败！若此错误频繁出现，请联系客服！" + reason.message, tab, funCallback);

    });

}
//获取下一页数据
async function AliBaBacallNextPage(contend, tab, funCallback) {
    BatchExecuteProductDetail(contend, tab, funCallback, () => {
        if (contend.next && contend.next != '')
            ALiBaBaCategoryCollect(contend, tab, funCallback);
        else
            funCallback({ "Type": "SetCategoryResult" }, tab, function (response) { });
    });
}

//批量采集
async function BatchExecuteProductDetail(contend, tab, sendToContent, funCallback) {
    let control = null;
    const tasks = new Array(contend.data.length).fill(0).map((v, i) => {
        return function task() {
            return new Promise((resolve) => {
                if (control && control.isStopped) {
                    resolve();
                    return;
                }
                ExecuteProductDetail(contend.data[i], contend.platformId, true, function (data) {
                    if (control && control.isStopped) {
                        resolve();
                        return;
                    }
                    // 命中采集箱上限时，立即停止后续批次
                    if (data && data.MessageType && data.MessageType == "error" && data.Message == CATEGORY_SAVE_LIMIT_MESSAGE) {
                        control.stop();
                        sendToContent({ "Type": "Alter", "MessageType": "error", "Message": data.Message }, tab, function (response) { });
                        sendToContent({ "Type": "CheckCategoryBtnDisabled", "Disabled": false }, tab, function (response) { });
                        resolve();
                    } else if (data.CollectBoxId) { //重复采集的
                        sendToContent({ "Type": "SetCategoryProgress", "data": data, "ProcessType": 1 }, tab, function (response) { });
                        resolve();
                    } else {
                        if (data.MessageType && data.MessageType == "success") {//采集成功
                            sendToContent({ "Type": "SetCategoryProgress", "ProcessType": 2 }, tab, function (response) { });
                            resolve();
                        } else if (data.MessageType && data.MessageType == "error") {//采集失败
                            sendToContent({ "Type": "SetCategoryProgress", "ProcessType": 3, "url": contend.data[i] }, tab, function (response) { });
                            resolve();
                        } else {
                            // console.log(data);
                        }
                    }
                });
            })
        }
    })
    const Control = new ConcurrencyControl(tasks, 2, funCallback)
    control = Control
    Control.runTask() // 执行队列任务
};
function ExecuteProductDetail(url, platformId, isVerifyDuplicate, funCallback) {

    try {
        if (isVerifyDuplicate) {
            GetSourceUrlEntity(url,
                function (sku) { // 获取采集过的产品数据成功的回调
                    if (sku !== null) {
                        funCallback(sku)
                    }
                    else {
                        AnalyticalProducts(platformId, { isLinkCollect: true }, null, url, funCallback);
                    }
                },
                function (msg) {
                    // 获取采集过的产品数据失败的回调 —— failedCallBack
                    funCallback({ 'MessageType': "error", "Message": msg })
                }
            );
        } else {
            AnalyticalProducts(platformId, { isLinkCollect: true }, null, url, funCallback);
        }
    } catch (error) {
        funCallback({ 'MessageType': "error", "Message": error })
    }
}

function GetSourceUrlEntity(sourceUrl, successfulCallBack, failedCallBack) {
    request(config.url.getSourceUrlEntity(), { responseType: "json", body: { "SourceUrl": sourceUrl }, method: "POST" }).then(res => {
        if (res !== null) {
            if (res.IsSuccess === true) {
                successfulCallBack(res.Data);
            } else {
                failedCallBack(res.Message == null ? (res.ResponseError == null ? "服务器未知异常，请联系管理员" : res.ResponseError.Message) : res.Message);
            }
        } else {
            failedCallBack("发生未知异常！请稍后重试！若长时间发生此错误，请与客服联系！");
        }
    }).catch(reason => {
        failedCallBack("服务器连接失败！请稍后重试！若长时间发生此错误，请与客服联系！");
    });
}

function CategroyErrorCall(msg, tab, funCallback) {
    funCallback({ "Type": "Alter", "MessageType": "error", "Message": msg }, tab, function (response) { });
    funCallback({ "Type": "CheckCategoryBtnDisabled", "Disabled": false }, tab, function (response) { });
}



var getCookie = function (name) {
    var arr = document.cookie.match(new RegExp("(^| )" + name + "=([^;]*)(;|$)"));
    if (arr != null) return unescape(arr[2]);
    return null
};
function AnalyticalMercadoliProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    let colorName = "";
    let variationImageArr = [];
    function getMoreData(products, pageHtml) {
        // 创建任务队列
        const tasks = new Array(products.length).fill(0).map((_, i) => {
            return function task() {
                return new Promise((resolve) => {
                    try {
                        let currentProduct = products[i];
                        funCallback({ "Type": "GetMercadoVariantData", "SouceUrl": souceUrl, "AttrId": currentProduct.attribute_id, "PermaLink": currentProduct.permalink, "ColorName": colorName }, tab, function (res) {
                            variationImageArr.push({
                                "AttrId": currentProduct.attribute_id,
                                "Images": res.data
                            })
                            resolve();
                        });
                    } catch (e) {
                        console.error("任务执行失败:", e);
                        resolve(); // 即使报错也调用 resolve 防止卡住队列
                    }
                });
            };
        });
        // 调用控制器 一次并发两个
        const Control = new ConcurrencyControl(tasks, 4, function () {
            let model = {
                Html: btoa(encodeURI(pageHtml)),
                SourcePlatform: 22,
                SouceUrl: souceUrl,
                MoreData: JSON.stringify(variationImageArr),
            };
            SaveLiknProduct(tab, model, funCallback);
        });
        Control.runTask(); // 执行队列任务
    }

    funCallback({ Type: "GetMercadoHtml", RequestUrl: souceUrl }, tab, function (response) {
        if (response.IsSuccess) {
            var data = response.Data;
            //console.log(data);
            if (data.indexOf("login?platform_id=ml") > -1) {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "未能获取到产品数据，请登录美客多商城账号后再尝试采集" }, tab, function (response) { });
                return;
            }

            typeof (data) == "object" && (data = JSON.stringify(data));
            funCallback({ "Type": "GetMercadoPageData", "HtmlStr": data }, tab, function (response) {
                let products = [];
                let outsideVariations = null;
                try {
                    outsideVariations = response.model.initialState.components.outside_variations;
                } catch { }
                if (!outsideVariations) {
                    funCallback({ "Type": "Alter", "MessageType": "error", "Message": "未能获取到产品数据，请检查是否登录美客多商城或打开产品详情页查看是否能正常访问" }, tab, function (response) { });
                    return;
                }

                try {
                    products = outsideVariations.pickers.find(x => x.id == "COLOR_SECONDARY_COLOR").products;
                    colorName = "COLOR_SECONDARY_COLOR";
                } catch { }

                if (products.length <= 0) {
                    try {
                        products = outsideVariations.pickers.find(x => x.id == "COLOR").products;
                        colorName = "COLOR";
                    } catch { }
                }

                if (products.length <= 0) {
                    try {
                        products = outsideVariations.pickers.find(x => x.label.text.toLowerCase().indexOf("color") >= 0).products;
                        colorName = "COLOR";
                    } catch { }
                }

                if (products.length > 1) {
                    getMoreData(products, data);
                } else {
                    var model = {
                        Html: btoa(encodeURI(data)),
                        SourcePlatform: 22,
                        SouceUrl: souceUrl
                    };
                    SaveLiknProduct(tab, model, funCallback);
                }
            });
        } else {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "未能获取到产品数据，请打开产品详情页查看是否能正常访问" }, tab, function (response) { });
        }
    });

    return;
}

//获取纯文本描述
function getSimpleText(html) {
    var re1 = new RegExp("</h([1-6])>", "g");
    var re2 = new RegExp("</p>", "g");
    var re3 = new RegExp("</li>", "g");
    var re4 = new RegExp("(&nbsp; ){1,}", "g");
    var re5 = new RegExp("(&nbsp;){1,}", "g");
    html = html.replace(re1, "\n");
    html = html.replace(re2, "\n");
    html = html.replace(re3, "\n");
    html = html.replace(re4, " ");
    html = html.replace(re5, " ");

    var re17 = new RegExp("<script[^>]*?>.*?</script>", "g");
    var re6 = new RegExp("<.+?>", "g");
    var msg = html.replace(re17, '');//执行替换成空字符
    msg = msg.replace(re6, '');//执行替换成空字符

    var re7 = new RegExp("&(quot|#34);", "g");
    var re8 = new RegExp("&(amp|#38);", "g");
    var re9 = new RegExp("&(lt|#60);", "g");
    var re10 = new RegExp("&(gt|#62);", "g");
    var re11 = new RegExp("&(nbsp|#160);", "g");
    var re12 = new RegExp("&(iexcl|#161);", "g");
    var re13 = new RegExp("&(cent|#162);", "g");
    var re14 = new RegExp("&(pound|#163);", "g");
    var re15 = new RegExp("&(copy|#169);", "g");
    var re16 = /&#(\d+);/g;
    msg = msg.replace(re7, '"');
    msg = msg.replace(re8, "&");
    msg = msg.replace(re9, "<");
    msg = msg.replace(re10, ">");
    msg = msg.replace(re11, " ");
    msg = msg.replace(re12, "\xa1");
    msg = msg.replace(re13, "\xa2");
    msg = msg.replace(re14, "\xa3");
    msg = msg.replace(re15, "\xa9");
    msg = msg.replace(re16, "");

    return msg;
}


function convertHtmlToPlainText(html) {
    if (!html || typeof html !== 'string') {
        return '';
    }

    let result = html;

    // 1. 移除 HTML 注释
    result = result.replace(/<!--[\s\S]*?-->/g, '');
    result = result.replace(/<title\b[^<]*(?:(?!<\/title>)<[^<]*)*<\/title>/gi, '');

    // 2. 彻底移除 <script>...</script> 块（含多行、属性）
    result = result.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

    // 3. 彻底移除 <style>...</style> 块
    result = result.replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '');

    // 4. 将需要换行的标签先转换为 \n（注意：必须在删除标签前处理！）
    //    包括：<br>, </p>, </div>, </li>, </h1>-</h6> 等块级结束标签
    result = result.replace(/<br\s*\/?>/gi, '\n');
    result = result.replace(/<\/(p|div|li|h[1-6]|ul|ol|blockquote|section|article|header|footer|aside|nav|main|form|table|tr|td|th|title)\s*>/gi, '\n');

    // 5. 删除所有剩余的 HTML 标签（包括 <title>, <meta>, <link>, <span> 等任何标签）
    result = result.replace(/<[^>]+>/g, '');

    // 6. 按行分割，去除每行开头的空白（保留行内文字空格）
    const lines = result.split('\n').map(line => line.trimStart());

    // 7. 合并回字符串
    result = lines.join('\n');
    result = result.replace(/&nbsp;/gi, ' ');

    // 8. 压缩多个连续空行为一个空行
    result = result.replace(/\n\s*\n/g, '\n\n');


    // 9. 去掉整个字符串首尾空白
    return result.trim();
}


function htmlEncodeByRegExp(str) {
    var s = "";
    if (str.length == 0) return "";
    s = str.replace(/&/g, "&amp;");
    s = s.replace(/</g, "&lt;");
    s = s.replace(/>/g, "&gt;");
    s = s.replace(/\s/g, "&nbsp;");
    s = s.replace(/\'/g, "&#39;");
    s = s.replace(/\"/g, "&quot;");
    return s;
}

function htmlDecodeByRegExp(str) {
    var s = "";
    if (str.length == 0) return "";
    s = str.replace(/&amp;/g, "&");
    s = s.replace(/&lt;/g, "<");
    s = s.replace(/&gt;/g, ">");
    s = s.replace(/&nbsp;/g, " ");
    s = s.replace(/&#39;/g, "\'");
    s = s.replace(/&#039;/g, "\'");
    s = s.replace(/&quot;/g, "\"");
    s = s.replace(/&#034;/g, "\"");
    return s;
}

//1688笛卡尔积
function DescartesByAlibaba(arr) {
    var result = [], point = [], count = 1, propertyName = [];
    for (var i = 0; i < arr.sku.skuProps.length; i++) {
        point.push(arr.sku.skuProps[i].value.length);
        count *= arr.sku.skuProps[i].value.length;
    }
    for (var i = 0; i < count; i++) {
        var _zb = [], _tmp = i;
        for (var j = point.length - 1; j > -1; j--) {
            _zb[j] = _tmp % point[j];
            _tmp = parseInt(_tmp / point[j]);
        }
        var _property = [];
        var _variantImageUrl = [];
        var keys = [];
        for (var k = 0; k < _zb.length; k++) {
            _property[k] = { "Key": arr.sku.skuProps[k].prop, "Value": getSimpleText(arr.sku.skuProps[k].value[_zb[k]].name) };
            keys.push(arr.sku.skuProps[k].value[_zb[k]].name);
            if (arr.sku.skuProps[k].value[_zb[k]].hasOwnProperty("imageUrl") && null != arr.sku.skuProps[k].value[_zb[k]].imageUrl && "" != arr.sku.skuProps[k].value[_zb[k]].imageUrl) {
                _variantImageUrl.push(arr.sku.skuProps[k].value[_zb[k]].imageUrl);
            }
            if (propertyName.indexOf(arr.sku.skuProps[k].prop) == -1) {
                propertyName.push(arr.sku.skuProps[k].prop);
            }
        }
        var key = keys.join("&gt;");
        if (arr.sku.skuMap.hasOwnProperty(key)) {
            var info = arr.sku.skuMap[key];
            var price = 0.0;
            if (info.discountPrice == null) {
                //没有变体的时候，价格在外面
                price = arr.sku.skuPriceScale.match(/\d+(.\d+)?/g)[0];
            } else {
                price = info.discountPrice + 0;
            }
            result.push({ "Property": _property, "VariantImageUrl": _variantImageUrl, "Price": price });
        }
    }
    return { "Skus": result, "PropertyName": propertyName };
}

//1688国际站笛卡尔积
function DescartesByAlibabaInternation(arr) {
    var result = [], point = [], count = 1, propertyName = [];
    for (var i = 0; i < arr.length; i++) {
        point.push(arr[i].values.length);
        count *= arr[i].values.length;
    }
    for (var i = 0; i < count; i++) {
        var _zb = [], _tmp = i;
        for (var j = point.length - 1; j > -1; j--) {
            _zb[j] = _tmp % point[j];
            _tmp = parseInt(_tmp / point[j]);
        }
        var _property = [];
        var _variantImageUrl = [];
        for (var k = 0; k < _zb.length; k++) {
            _property[k] = { "Key": arr[k].name, "Value": getSimpleText(arr[k].values[_zb[k]].name) };
            if (arr[k].values[_zb[k]].hasOwnProperty("originImage") && null != arr[k].values[_zb[k]].originImage && "" != arr[k].values[_zb[k]].originImage) {
                _variantImageUrl.push(arr[k].values[_zb[k]].originImage);
            }
            if (propertyName.indexOf(arr[k].name) == -1) {
                propertyName.push(arr[k].name);
            }
        }

        result.push({ "Property": _property, "VariantImageUrl": _variantImageUrl });
    }
    return { "Skus": result, "PropertyName": propertyName };
}
//Amazon对象笛卡尔积
function DescartesByAmazon(list) {
    //parent上一级索引;count指针计数
    var point = {};
    var result = [];
    var pIndex = null;
    var tempCount = 0;
    var temp = [];
    //根据参数列生成指针对象
    for (var index in list) {
        if (typeof list[index] == 'object') {
            point[index] = { 'parent': pIndex, 'count': 0 }
            pIndex = index;
        }
    }
    //单维度数据结构直接返回
    if (pIndex == null) {
        return list;
    }
    //动态生成笛卡尔积
    while (true) {
        for (var index in list) {
            tempCount = point[index]['count'];
            temp.push({ "Key": index, "Value": list[index][tempCount] });
            console.log({ "Key": index, "Value": list[index][tempCount] });
        }
        //压入结果数组
        result.push(temp);
        temp = [];
        //检查指针最大值问题
        while (true) {
            if (point[index]['count'] + 1 >= list[index].length) {
                point[index]['count'] = 0;
                pIndex = point[index]['parent'];
                if (pIndex == null) {
                    return result;
                }
                //赋值parent进行再次检查
                index = pIndex;
            }
            else {
                point[index]['count']++;
                break;
            }
        }
    }
}
//获取天猫笛卡尔集
function escartesByTmall(array) {
    if (array.length < 2) return array[0] || [];

    return array.reduce((total, currentValue) => {
        let res = [];

        total.forEach(t => {
            currentValue.forEach(cv => {
                if (t instanceof Array) 	// 或者使用 Array.isArray(t)
                    res.push([...t, cv]);
                else
                    res.push([t, cv]);
            })
        })
        return res;
    });
}

//获取shopee笛卡尔集
function escartesByShopee(array) {
    if (array.length < 2) return array[0] || [];

    return array.reduce((total, currentValue) => {
        let res = [];

        total.forEach(t => {
            currentValue.forEach(cv => {
                if (t instanceof Array) 	// 或者使用 Array.isArray(t)
                    res.push([...t, cv]);
                else
                    res.push([t, cv]);
            })
        })
        return res;
    });
}

//获取Cdiscount笛卡尔集
function escartesByCdiscount(arr) {
    var result = [], point = [], count = 1, propertyName = [];
    for (var i = 0; i < arr.length; i++) {
        point.push(arr[i].value.length);
        count *= arr[i].value.length;
    }
    for (var i = 0; i < count; i++) {
        var _zb = [], _tmp = i;
        for (var j = point.length - 1; j > -1; j--) {
            _zb[j] = _tmp % point[j];
            _tmp = parseInt(_tmp / point[j]);
        }
        var _property = [];
        var _variantImageUrl = [];
        for (var k = 0; k < _zb.length; k++) {
            _property[k] = { "Key": arr[k].key, "Value": getSimpleText(arr[k].value[_zb[k]].option) };
            if (arr[k].value[_zb[k]].hasOwnProperty("imageUrl") && null != arr[k].value[_zb[k]].imageUrl && "" != arr[k].value[_zb[k]].imageUrl) {
                _variantImageUrl.push(arr[k].value[_zb[k]].imageUrl);
            }
            if (propertyName.indexOf(arr[k].key) == -1) {
                propertyName.push(arr[k].key);
            }
        }
        result.push({ "Property": _property, "VariantImageUrl": _variantImageUrl });
    }
    return { "Skus": result, "PropertyName": propertyName };
}

function replaceEmoji(content) {
    return content.replace(/(?:[\u2700-\u27bf]|(?:\ud83c[\udde6-\uddff]){2}|[\ud800-\udbff][\udc00-\udfff]|[\u0023-\u0039]\ufe0f?\u20e3|\u3299|\u3297|\u303d|\u3030|\u24c2|\ud83c[\udd70-\udd71]|\ud83c[\udd7e-\udd7f]|\ud83c\udd8e|\ud83c[\udd91-\udd9a]|\ud83c[\udde6-\uddff]|\ud83c[\ude01-\ude02]|\ud83c\ude1a|\ud83c\ude2f|\ud83c[\ude32-\ude3a]|\ud83c[\ude50-\ude51]|\u203c|\u2049|[\u25aa-\u25ab]|\u25b6|\u25c0|[\u25fb-\u25fe]|\u00a9|\u00ae|\u2122|\u2139|\ud83c\udc04|[\u2600-\u26FF]|\u2b05|\u2b06|\u2b07|\u2b1b|\u2b1c|\u2b50|\u2b55|\u231a|\u231b|\u2328|\u23cf|[\u23e9-\u23f3]|[\u23f8-\u23fa]|\ud83c\udccf|\u2934|\u2935|[\u2190-\u21ff])/g, "");
}
//获取天猫图文描述签名
function getTmallSign(cookies, t, data) {
    return function (e) {
        function t(e, t) {
            return e << t | e >>> 32 - t
        }
        function n(e, t) {
            var n, r, i, a, o;
            return i = 2147483648 & e,
                a = 2147483648 & t,
                o = (1073741823 & e) + (1073741823 & t),
                (n = 1073741824 & e) & (r = 1073741824 & t) ? 2147483648 ^ o ^ i ^ a : n | r ? 1073741824 & o ? 3221225472 ^ o ^ i ^ a : 1073741824 ^ o ^ i ^ a : o ^ i ^ a
        }
        function r(e, r, i, a, o, s, l) {
            return e = n(e, n(n(function (e, t, n) {
                return e & t | ~e & n
            }(r, i, a), o), l)),
                n(t(e, s), r)
        }
        function i(e, r, i, a, o, s, l) {
            return e = n(e, n(n(function (e, t, n) {
                return e & n | t & ~n
            }(r, i, a), o), l)),
                n(t(e, s), r)
        }
        function a(e, r, i, a, o, s, l) {
            return e = n(e, n(n(function (e, t, n) {
                return e ^ t ^ n
            }(r, i, a), o), l)),
                n(t(e, s), r)
        }
        function o(e, r, i, a, o, s, l) {
            return e = n(e, n(n(function (e, t, n) {
                return t ^ (e | ~n)
            }(r, i, a), o), l)),
                n(t(e, s), r)
        }
        function s(e) {
            var t, n = "", r = "";
            for (t = 0; 3 >= t; t++)
                n += (r = "0" + (e >>> 8 * t & 255).toString(16)).substr(r.length - 2, 2);
            return n
        }
        var l, c, p, u, d, f, m, g, h, v;
        for (v = function (e) {
            for (var t, n = e.length, r = n + 8, i = 16 * ((r - r % 64) / 64 + 1), a = new Array(i - 1), o = 0, s = 0; n > s;)
                o = s % 4 * 8,
                    a[t = (s - s % 4) / 4] = a[t] | e.charCodeAt(s) << o,
                    s++;
            return o = s % 4 * 8,
                a[t = (s - s % 4) / 4] = a[t] | 128 << o,
                a[i - 2] = n << 3,
                a[i - 1] = n >>> 29,
                a
        }(e = function (e) {
            e = e.replace(/\r\n/g, "\n");
            for (var t = "", n = 0; n < e.length; n++) {
                var r = e.charCodeAt(n);
                128 > r ? t += String.fromCharCode(r) : r > 127 && 2048 > r ? (t += String.fromCharCode(r >> 6 | 192),
                    t += String.fromCharCode(63 & r | 128)) : (t += String.fromCharCode(r >> 12 | 224),
                        t += String.fromCharCode(r >> 6 & 63 | 128),
                        t += String.fromCharCode(63 & r | 128))
            }
            return t
        }(e)),
            f = 1732584193,
            m = 4023233417,
            g = 2562383102,
            h = 271733878,
            l = 0; l < v.length; l += 16)
            c = f,
                p = m,
                u = g,
                d = h,
                f = r(f, m, g, h, v[l + 0], 7, 3614090360),
                h = r(h, f, m, g, v[l + 1], 12, 3905402710),
                g = r(g, h, f, m, v[l + 2], 17, 606105819),
                m = r(m, g, h, f, v[l + 3], 22, 3250441966),
                f = r(f, m, g, h, v[l + 4], 7, 4118548399),
                h = r(h, f, m, g, v[l + 5], 12, 1200080426),
                g = r(g, h, f, m, v[l + 6], 17, 2821735955),
                m = r(m, g, h, f, v[l + 7], 22, 4249261313),
                f = r(f, m, g, h, v[l + 8], 7, 1770035416),
                h = r(h, f, m, g, v[l + 9], 12, 2336552879),
                g = r(g, h, f, m, v[l + 10], 17, 4294925233),
                m = r(m, g, h, f, v[l + 11], 22, 2304563134),
                f = r(f, m, g, h, v[l + 12], 7, 1804603682),
                h = r(h, f, m, g, v[l + 13], 12, 4254626195),
                g = r(g, h, f, m, v[l + 14], 17, 2792965006),
                f = i(f, m = r(m, g, h, f, v[l + 15], 22, 1236535329), g, h, v[l + 1], 5, 4129170786),
                h = i(h, f, m, g, v[l + 6], 9, 3225465664),
                g = i(g, h, f, m, v[l + 11], 14, 643717713),
                m = i(m, g, h, f, v[l + 0], 20, 3921069994),
                f = i(f, m, g, h, v[l + 5], 5, 3593408605),
                h = i(h, f, m, g, v[l + 10], 9, 38016083),
                g = i(g, h, f, m, v[l + 15], 14, 3634488961),
                m = i(m, g, h, f, v[l + 4], 20, 3889429448),
                f = i(f, m, g, h, v[l + 9], 5, 568446438),
                h = i(h, f, m, g, v[l + 14], 9, 3275163606),
                g = i(g, h, f, m, v[l + 3], 14, 4107603335),
                m = i(m, g, h, f, v[l + 8], 20, 1163531501),
                f = i(f, m, g, h, v[l + 13], 5, 2850285829),
                h = i(h, f, m, g, v[l + 2], 9, 4243563512),
                g = i(g, h, f, m, v[l + 7], 14, 1735328473),
                f = a(f, m = i(m, g, h, f, v[l + 12], 20, 2368359562), g, h, v[l + 5], 4, 4294588738),
                h = a(h, f, m, g, v[l + 8], 11, 2272392833),
                g = a(g, h, f, m, v[l + 11], 16, 1839030562),
                m = a(m, g, h, f, v[l + 14], 23, 4259657740),
                f = a(f, m, g, h, v[l + 1], 4, 2763975236),
                h = a(h, f, m, g, v[l + 4], 11, 1272893353),
                g = a(g, h, f, m, v[l + 7], 16, 4139469664),
                m = a(m, g, h, f, v[l + 10], 23, 3200236656),
                f = a(f, m, g, h, v[l + 13], 4, 681279174),
                h = a(h, f, m, g, v[l + 0], 11, 3936430074),
                g = a(g, h, f, m, v[l + 3], 16, 3572445317),
                m = a(m, g, h, f, v[l + 6], 23, 76029189),
                f = a(f, m, g, h, v[l + 9], 4, 3654602809),
                h = a(h, f, m, g, v[l + 12], 11, 3873151461),
                g = a(g, h, f, m, v[l + 15], 16, 530742520),
                f = o(f, m = a(m, g, h, f, v[l + 2], 23, 3299628645), g, h, v[l + 0], 6, 4096336452),
                h = o(h, f, m, g, v[l + 7], 10, 1126891415),
                g = o(g, h, f, m, v[l + 14], 15, 2878612391),
                m = o(m, g, h, f, v[l + 5], 21, 4237533241),
                f = o(f, m, g, h, v[l + 12], 6, 1700485571),
                h = o(h, f, m, g, v[l + 3], 10, 2399980690),
                g = o(g, h, f, m, v[l + 10], 15, 4293915773),
                m = o(m, g, h, f, v[l + 1], 21, 2240044497),
                f = o(f, m, g, h, v[l + 8], 6, 1873313359),
                h = o(h, f, m, g, v[l + 15], 10, 4264355552),
                g = o(g, h, f, m, v[l + 6], 15, 2734768916),
                m = o(m, g, h, f, v[l + 13], 21, 1309151649),
                f = o(f, m, g, h, v[l + 4], 6, 4149444226),
                h = o(h, f, m, g, v[l + 11], 10, 3174756917),
                g = o(g, h, f, m, v[l + 2], 15, 718787259),
                m = o(m, g, h, f, v[l + 9], 21, 3951481745),
                f = n(f, c),
                m = n(m, p),
                g = n(g, u),
                h = n(h, d);
        return (s(f) + s(m) + s(g) + s(h)).toLowerCase()
    }(cookies + "&" + t + "&12574478&" + data);
}

//获取天猫数据签名
function getTmallDataSign(cookies, t, data) {
    return function (a) {
        function b(a, b) {
            return a << b | a >>> 32 - b
        }
        function c(a, b) {
            var c, d, e, f, g;
            return e = 2147483648 & a,
                f = 2147483648 & b,
                c = 1073741824 & a,
                d = 1073741824 & b,
                g = (1073741823 & a) + (1073741823 & b),
                c & d ? 2147483648 ^ g ^ e ^ f : c | d ? 1073741824 & g ? 3221225472 ^ g ^ e ^ f : 1073741824 ^ g ^ e ^ f : g ^ e ^ f
        }
        function d(a, b, c) {
            return a & b | ~a & c
        }
        function e(a, b, c) {
            return a & c | b & ~c
        }
        function f(a, b, c) {
            return a ^ b ^ c
        }
        function g(a, b, c) {
            return b ^ (a | ~c)
        }
        function h(a, e, f, g, h, i, j) {
            return a = c(a, c(c(d(e, f, g), h), j)),
                c(b(a, i), e)
        }
        function i(a, d, f, g, h, i, j) {
            return a = c(a, c(c(e(d, f, g), h), j)),
                c(b(a, i), d)
        }
        function j(a, d, e, g, h, i, j) {
            return a = c(a, c(c(f(d, e, g), h), j)),
                c(b(a, i), d)
        }
        function k(a, d, e, f, h, i, j) {
            return a = c(a, c(c(g(d, e, f), h), j)),
                c(b(a, i), d)
        }
        function l(a) {
            for (var b, c = a.length, d = c + 8, e = (d - d % 64) / 64, f = 16 * (e + 1), g = new Array(f - 1), h = 0, i = 0; c > i;)
                b = (i - i % 4) / 4,
                    h = i % 4 * 8,
                    g[b] = g[b] | a.charCodeAt(i) << h,
                    i++;
            return b = (i - i % 4) / 4,
                h = i % 4 * 8,
                g[b] = g[b] | 128 << h,
                g[f - 2] = c << 3,
                g[f - 1] = c >>> 29,
                g
        }
        function m(a) {
            var b, c, d = "", e = "";
            for (c = 0; 3 >= c; c++)
                b = a >>> 8 * c & 255,
                    e = "0" + b.toString(16),
                    d += e.substr(e.length - 2, 2);
            return d
        }
        function n(a) {
            a = a.replace(/\r\n/g, "\n");
            for (var b = "", c = 0; c < a.length; c++) {
                var d = a.charCodeAt(c);
                128 > d ? b += String.fromCharCode(d) : d > 127 && 2048 > d ? (b += String.fromCharCode(d >> 6 | 192),
                    b += String.fromCharCode(63 & d | 128)) : (b += String.fromCharCode(d >> 12 | 224),
                        b += String.fromCharCode(d >> 6 & 63 | 128),
                        b += String.fromCharCode(63 & d | 128))
            }
            return b
        }
        var o, p, q, r, s, t, u, v, w, x = [], y = 7, z = 12, A = 17, B = 22, C = 5, D = 9, E = 14, F = 20, G = 4, H = 11, I = 16, J = 23, K = 6, L = 10, M = 15, N = 21;
        for (a = n(a),
            x = l(a),
            t = 1732584193,
            u = 4023233417,
            v = 2562383102,
            w = 271733878,
            o = 0; o < x.length; o += 16)
            p = t,
                q = u,
                r = v,
                s = w,
                t = h(t, u, v, w, x[o + 0], y, 3614090360),
                w = h(w, t, u, v, x[o + 1], z, 3905402710),
                v = h(v, w, t, u, x[o + 2], A, 606105819),
                u = h(u, v, w, t, x[o + 3], B, 3250441966),
                t = h(t, u, v, w, x[o + 4], y, 4118548399),
                w = h(w, t, u, v, x[o + 5], z, 1200080426),
                v = h(v, w, t, u, x[o + 6], A, 2821735955),
                u = h(u, v, w, t, x[o + 7], B, 4249261313),
                t = h(t, u, v, w, x[o + 8], y, 1770035416),
                w = h(w, t, u, v, x[o + 9], z, 2336552879),
                v = h(v, w, t, u, x[o + 10], A, 4294925233),
                u = h(u, v, w, t, x[o + 11], B, 2304563134),
                t = h(t, u, v, w, x[o + 12], y, 1804603682),
                w = h(w, t, u, v, x[o + 13], z, 4254626195),
                v = h(v, w, t, u, x[o + 14], A, 2792965006),
                u = h(u, v, w, t, x[o + 15], B, 1236535329),
                t = i(t, u, v, w, x[o + 1], C, 4129170786),
                w = i(w, t, u, v, x[o + 6], D, 3225465664),
                v = i(v, w, t, u, x[o + 11], E, 643717713),
                u = i(u, v, w, t, x[o + 0], F, 3921069994),
                t = i(t, u, v, w, x[o + 5], C, 3593408605),
                w = i(w, t, u, v, x[o + 10], D, 38016083),
                v = i(v, w, t, u, x[o + 15], E, 3634488961),
                u = i(u, v, w, t, x[o + 4], F, 3889429448),
                t = i(t, u, v, w, x[o + 9], C, 568446438),
                w = i(w, t, u, v, x[o + 14], D, 3275163606),
                v = i(v, w, t, u, x[o + 3], E, 4107603335),
                u = i(u, v, w, t, x[o + 8], F, 1163531501),
                t = i(t, u, v, w, x[o + 13], C, 2850285829),
                w = i(w, t, u, v, x[o + 2], D, 4243563512),
                v = i(v, w, t, u, x[o + 7], E, 1735328473),
                u = i(u, v, w, t, x[o + 12], F, 2368359562),
                t = j(t, u, v, w, x[o + 5], G, 4294588738),
                w = j(w, t, u, v, x[o + 8], H, 2272392833),
                v = j(v, w, t, u, x[o + 11], I, 1839030562),
                u = j(u, v, w, t, x[o + 14], J, 4259657740),
                t = j(t, u, v, w, x[o + 1], G, 2763975236),
                w = j(w, t, u, v, x[o + 4], H, 1272893353),
                v = j(v, w, t, u, x[o + 7], I, 4139469664),
                u = j(u, v, w, t, x[o + 10], J, 3200236656),
                t = j(t, u, v, w, x[o + 13], G, 681279174),
                w = j(w, t, u, v, x[o + 0], H, 3936430074),
                v = j(v, w, t, u, x[o + 3], I, 3572445317),
                u = j(u, v, w, t, x[o + 6], J, 76029189),
                t = j(t, u, v, w, x[o + 9], G, 3654602809),
                w = j(w, t, u, v, x[o + 12], H, 3873151461),
                v = j(v, w, t, u, x[o + 15], I, 530742520),
                u = j(u, v, w, t, x[o + 2], J, 3299628645),
                t = k(t, u, v, w, x[o + 0], K, 4096336452),
                w = k(w, t, u, v, x[o + 7], L, 1126891415),
                v = k(v, w, t, u, x[o + 14], M, 2878612391),
                u = k(u, v, w, t, x[o + 5], N, 4237533241),
                t = k(t, u, v, w, x[o + 12], K, 1700485571),
                w = k(w, t, u, v, x[o + 3], L, 2399980690),
                v = k(v, w, t, u, x[o + 10], M, 4293915773),
                u = k(u, v, w, t, x[o + 1], N, 2240044497),
                t = k(t, u, v, w, x[o + 8], K, 1873313359),
                w = k(w, t, u, v, x[o + 15], L, 4264355552),
                v = k(v, w, t, u, x[o + 6], M, 2734768916),
                u = k(u, v, w, t, x[o + 13], N, 1309151649),
                t = k(t, u, v, w, x[o + 4], K, 4149444226),
                w = k(w, t, u, v, x[o + 11], L, 3174756917),
                v = k(v, w, t, u, x[o + 2], M, 718787259),
                u = k(u, v, w, t, x[o + 9], N, 3951481745),
                t = c(t, p),
                u = c(u, q),
                v = c(v, r),
                w = c(w, s);
        var O = m(t) + m(u) + m(v) + m(w);
        return O.toLowerCase()
    }(cookies + "&" + t + "&12574478&" + data);
}

//获取1688数据签名
function getAlibabaCategorySign(cookies, t, data) {
    return function (e) {
        function t(e, t) {
            return e << t | e >>> 32 - t
        }
        function o(e, t) {
            var o, n, r, i, a;
            return r = 2147483648 & e,
                i = 2147483648 & t,
                a = (1073741823 & e) + (1073741823 & t),
                (o = 1073741824 & e) & (n = 1073741824 & t) ? 2147483648 ^ a ^ r ^ i : o | n ? 1073741824 & a ? 3221225472 ^ a ^ r ^ i : 1073741824 ^ a ^ r ^ i : a ^ r ^ i
        }
        function n(e, n, r, i, a, s, u) {
            return o(t(e = o(e, o(o(function (e, t, o) {
                return e & t | ~e & o
            }(n, r, i), a), u)), s), n)
        }
        function r(e, n, r, i, a, s, u) {
            return o(t(e = o(e, o(o(function (e, t, o) {
                return e & o | t & ~o
            }(n, r, i), a), u)), s), n)
        }
        function i(e, n, r, i, a, s, u) {
            return o(t(e = o(e, o(o(function (e, t, o) {
                return e ^ t ^ o
            }(n, r, i), a), u)), s), n)
        }
        function a(e, n, r, i, a, s, u) {
            return o(t(e = o(e, o(o(function (e, t, o) {
                return t ^ (e | ~o)
            }(n, r, i), a), u)), s), n)
        }
        function s(e) {
            var t, o = "", n = "";
            for (t = 0; 3 >= t; t++)
                o += (n = "0" + (e >>> 8 * t & 255).toString(16)).substr(n.length - 2, 2);
            return o
        }
        var u, l, d, c, p, f, h, m, y, g;
        for (g = function (e) {
            for (var t = e.length, o = t + 8, n = 16 * ((o - o % 64) / 64 + 1), r = Array(n - 1), i = 0, a = 0; t > a;)
                i = a % 4 * 8,
                    r[(a - a % 4) / 4] |= e.charCodeAt(a) << i,
                    a++;
            return i = a % 4 * 8,
                r[(a - a % 4) / 4] |= 128 << i,
                r[n - 2] = t << 3,
                r[n - 1] = t >>> 29,
                r
        }(e = function (e) {
            var t = String.fromCharCode;
            e = e.replace(/\r\n/g, "\n");
            for (var o, n = "", r = 0; r < e.length; r++)
                128 > (o = e.charCodeAt(r)) ? n += t(o) : o > 127 && 2048 > o ? (n += t(o >> 6 | 192),
                    n += t(63 & o | 128)) : (n += t(o >> 12 | 224),
                        n += t(o >> 6 & 63 | 128),
                        n += t(63 & o | 128));
            return n
        }(e)),
            f = 1732584193,
            h = 4023233417,
            m = 2562383102,
            y = 271733878,
            u = 0; u < g.length; u += 16)
            l = f,
                d = h,
                c = m,
                p = y,
                h = a(h = a(h = a(h = a(h = i(h = i(h = i(h = i(h = r(h = r(h = r(h = r(h = n(h = n(h = n(h = n(h, m = n(m, y = n(y, f = n(f, h, m, y, g[u + 0], 7, 3614090360), h, m, g[u + 1], 12, 3905402710), f, h, g[u + 2], 17, 606105819), y, f, g[u + 3], 22, 3250441966), m = n(m, y = n(y, f = n(f, h, m, y, g[u + 4], 7, 4118548399), h, m, g[u + 5], 12, 1200080426), f, h, g[u + 6], 17, 2821735955), y, f, g[u + 7], 22, 4249261313), m = n(m, y = n(y, f = n(f, h, m, y, g[u + 8], 7, 1770035416), h, m, g[u + 9], 12, 2336552879), f, h, g[u + 10], 17, 4294925233), y, f, g[u + 11], 22, 2304563134), m = n(m, y = n(y, f = n(f, h, m, y, g[u + 12], 7, 1804603682), h, m, g[u + 13], 12, 4254626195), f, h, g[u + 14], 17, 2792965006), y, f, g[u + 15], 22, 1236535329), m = r(m, y = r(y, f = r(f, h, m, y, g[u + 1], 5, 4129170786), h, m, g[u + 6], 9, 3225465664), f, h, g[u + 11], 14, 643717713), y, f, g[u + 0], 20, 3921069994), m = r(m, y = r(y, f = r(f, h, m, y, g[u + 5], 5, 3593408605), h, m, g[u + 10], 9, 38016083), f, h, g[u + 15], 14, 3634488961), y, f, g[u + 4], 20, 3889429448), m = r(m, y = r(y, f = r(f, h, m, y, g[u + 9], 5, 568446438), h, m, g[u + 14], 9, 3275163606), f, h, g[u + 3], 14, 4107603335), y, f, g[u + 8], 20, 1163531501), m = r(m, y = r(y, f = r(f, h, m, y, g[u + 13], 5, 2850285829), h, m, g[u + 2], 9, 4243563512), f, h, g[u + 7], 14, 1735328473), y, f, g[u + 12], 20, 2368359562), m = i(m, y = i(y, f = i(f, h, m, y, g[u + 5], 4, 4294588738), h, m, g[u + 8], 11, 2272392833), f, h, g[u + 11], 16, 1839030562), y, f, g[u + 14], 23, 4259657740), m = i(m, y = i(y, f = i(f, h, m, y, g[u + 1], 4, 2763975236), h, m, g[u + 4], 11, 1272893353), f, h, g[u + 7], 16, 4139469664), y, f, g[u + 10], 23, 3200236656), m = i(m, y = i(y, f = i(f, h, m, y, g[u + 13], 4, 681279174), h, m, g[u + 0], 11, 3936430074), f, h, g[u + 3], 16, 3572445317), y, f, g[u + 6], 23, 76029189), m = i(m, y = i(y, f = i(f, h, m, y, g[u + 9], 4, 3654602809), h, m, g[u + 12], 11, 3873151461), f, h, g[u + 15], 16, 530742520), y, f, g[u + 2], 23, 3299628645), m = a(m, y = a(y, f = a(f, h, m, y, g[u + 0], 6, 4096336452), h, m, g[u + 7], 10, 1126891415), f, h, g[u + 14], 15, 2878612391), y, f, g[u + 5], 21, 4237533241), m = a(m, y = a(y, f = a(f, h, m, y, g[u + 12], 6, 1700485571), h, m, g[u + 3], 10, 2399980690), f, h, g[u + 10], 15, 4293915773), y, f, g[u + 1], 21, 2240044497), m = a(m, y = a(y, f = a(f, h, m, y, g[u + 8], 6, 1873313359), h, m, g[u + 15], 10, 4264355552), f, h, g[u + 6], 15, 2734768916), y, f, g[u + 13], 21, 1309151649), m = a(m, y = a(y, f = a(f, h, m, y, g[u + 4], 6, 4149444226), h, m, g[u + 11], 10, 3174756917), f, h, g[u + 2], 15, 718787259), y, f, g[u + 9], 21, 3951481745),
                f = o(f, l),
                h = o(h, d),
                m = o(m, c),
                y = o(y, p);
        return (s(f) + s(h) + s(m) + s(y)).toLowerCase();
    }(cookies + "&" + t + "&12574478&" + data);
}

//获取Url中的参数
function getUrlQuery(url) {
    // str为？之后的参数部分字符串
    let str = url;
    if (str.indexOf("?") !== -1)
        str = str.substr(str.indexOf('?') + 1);
    // arr每个元素都是完整的参数键值
    const arr = str.split('&')
    // result为存储参数键值的集合
    const result = {}
    for (let i = 0; i < arr.length; i++) {
        // item的两个元素分别为参数名和参数值
        const item = arr[i].split('=')
        result[item[0]] = item[1]
    }
    return result;
}

function safeAdd(x, y) {
    var lsw = (x & 0xffff) + (y & 0xffff); var msw = (x >> 16) + (y >> 16) + (lsw >> 16); return (msw << 16) | (lsw & 0xffff)
}
function bitRotateLeft(num, cnt) {
    return (num << cnt) | (num >>> (32 - cnt))
}
function md5cmn(q, a, b, x, s, t) {
    return safeAdd(bitRotateLeft(safeAdd(safeAdd(a, q), safeAdd(x, t)), s), b)
}
function md5ff(a, b, c, d, x, s, t) {
    return md5cmn((b & c) | (~b & d), a, b, x, s, t)
}
function md5gg(a, b, c, d, x, s, t) {
    return md5cmn((b & d) | (c & ~d), a, b, x, s, t)
}
function md5hh(a, b, c, d, x, s, t) {
    return md5cmn(b ^ c ^ d, a, b, x, s, t)
}
function md5ii(a, b, c, d, x, s, t) {
    return md5cmn(c ^ (b | ~d), a, b, x, s, t)
}
function binlMD5(x, len) {
    x[len >> 5] |= 0x80 << (len % 32); x[((len + 64) >>> 9 << 4) + 14] = len;
    var i
    var olda
    var oldb
    var oldc
    var oldd
    var a = 1732584193
    var b = -271733879
    var c = -1732584194
    var d = 271733878
    for (i = 0; i < x.length; i += 16) {
        olda = a; oldb = b; oldc = c; oldd = d; a = md5ff(a, b, c, d, x[i], 7, -680876936); d = md5ff(d, a, b, c, x[i + 1], 12, -389564586); c = md5ff(c, d, a, b, x[i + 2], 17, 606105819); b = md5ff(b, c, d, a, x[i + 3], 22, -1044525330); a = md5ff(a, b, c, d, x[i + 4], 7, -176418897); d = md5ff(d, a, b, c, x[i + 5], 12, 1200080426); c = md5ff(c, d, a, b, x[i + 6], 17, -1473231341); b = md5ff(b, c, d, a, x[i + 7], 22, -45705983); a = md5ff(a, b, c, d, x[i + 8], 7, 1770035416); d = md5ff(d, a, b, c, x[i + 9], 12, -1958414417); c = md5ff(c, d, a, b, x[i + 10], 17, -42063); b = md5ff(b, c, d, a, x[i + 11], 22, -1990404162); a = md5ff(a, b, c, d, x[i + 12], 7, 1804603682); d = md5ff(d, a, b, c, x[i + 13], 12, -40341101); c = md5ff(c, d, a, b, x[i + 14], 17, -1502002290); b = md5ff(b, c, d, a, x[i + 15], 22, 1236535329); a = md5gg(a, b, c, d, x[i + 1], 5, -165796510); d = md5gg(d, a, b, c, x[i + 6], 9, -1069501632); c = md5gg(c, d, a, b, x[i + 11], 14, 643717713); b = md5gg(b, c, d, a, x[i], 20, -373897302); a = md5gg(a, b, c, d, x[i + 5], 5, -701558691); d = md5gg(d, a, b, c, x[i + 10], 9, 38016083); c = md5gg(c, d, a, b, x[i + 15], 14, -660478335); b = md5gg(b, c, d, a, x[i + 4], 20, -405537848); a = md5gg(a, b, c, d, x[i + 9], 5, 568446438); d = md5gg(d, a, b, c, x[i + 14], 9, -1019803690); c = md5gg(c, d, a, b, x[i + 3], 14, -187363961); b = md5gg(b, c, d, a, x[i + 8], 20, 1163531501); a = md5gg(a, b, c, d, x[i + 13], 5, -1444681467); d = md5gg(d, a, b, c, x[i + 2], 9, -51403784); c = md5gg(c, d, a, b, x[i + 7], 14, 1735328473); b = md5gg(b, c, d, a, x[i + 12], 20, -1926607734); a = md5hh(a, b, c, d, x[i + 5], 4, -378558); d = md5hh(d, a, b, c, x[i + 8], 11, -2022574463); c = md5hh(c, d, a, b, x[i + 11], 16, 1839030562); b = md5hh(b, c, d, a, x[i + 14], 23, -35309556); a = md5hh(a, b, c, d, x[i + 1], 4, -1530992060); d = md5hh(d, a, b, c, x[i + 4], 11, 1272893353); c = md5hh(c, d, a, b, x[i + 7], 16, -155497632); b = md5hh(b, c, d, a, x[i + 10], 23, -1094730640); a = md5hh(a, b, c, d, x[i + 13], 4, 681279174); d = md5hh(d, a, b, c, x[i], 11, -358537222); c = md5hh(c, d, a, b, x[i + 3], 16, -722521979); b = md5hh(b, c, d, a, x[i + 6], 23, 76029189); a = md5hh(a, b, c, d, x[i + 9], 4, -640364487); d = md5hh(d, a, b, c, x[i + 12], 11, -421815835); c = md5hh(c, d, a, b, x[i + 15], 16, 530742520); b = md5hh(b, c, d, a, x[i + 2], 23, -995338651); a = md5ii(a, b, c, d, x[i], 6, -198630844); d = md5ii(d, a, b, c, x[i + 7], 10, 1126891415); c = md5ii(c, d, a, b, x[i + 14], 15, -1416354905); b = md5ii(b, c, d, a, x[i + 5], 21, -57434055); a = md5ii(a, b, c, d, x[i + 12], 6, 1700485571); d = md5ii(d, a, b, c, x[i + 3], 10, -1894986606); c = md5ii(c, d, a, b, x[i + 10], 15, -1051523); b = md5ii(b, c, d, a, x[i + 1], 21, -2054922799); a = md5ii(a, b, c, d, x[i + 8], 6, 1873313359); d = md5ii(d, a, b, c, x[i + 15], 10, -30611744); c = md5ii(c, d, a, b, x[i + 6], 15, -1560198380); b = md5ii(b, c, d, a, x[i + 13], 21, 1309151649); a = md5ii(a, b, c, d, x[i + 4], 6, -145523070); d = md5ii(d, a, b, c, x[i + 11], 10, -1120210379); c = md5ii(c, d, a, b, x[i + 2], 15, 718787259); b = md5ii(b, c, d, a, x[i + 9], 21, -343485551); a = safeAdd(a, olda); b = safeAdd(b, oldb); c = safeAdd(c, oldc); d = safeAdd(d, oldd)
    }
    return [a, b, c, d]
}
function binl2rstr(input) {
    var i
    var output = ''
    var length32 = input.length * 32
    for (i = 0; i < length32; i += 8) {
        output += String.fromCharCode((input[i >> 5] >>> (i % 32)) & 0xff)
    }
    return output
}
function rstr2binl(input) {
    var i
    var output = []; output[(input.length >> 2) - 1] = undefined
    for (i = 0; i < output.length; i += 1) {
        output[i] = 0
    }
    var length8 = input.length * 8
    for (i = 0; i < length8; i += 8) {
        output[i >> 5] |= (input.charCodeAt(i / 8) & 0xff) << (i % 32)
    }
    return output
}
function rstrMD5(s) {
    return binl2rstr(binlMD5(rstr2binl(s), s.length * 8))
}
function rstrHMACMD5(key, data) {
    var i
    var bkey = rstr2binl(key); var ipad = []
    var opad = []
    var hash; ipad[15] = opad[15] = undefined
    if (bkey.length > 16) {
        bkey = binlMD5(bkey, key.length * 8)
    }
    for (i = 0; i < 16; i += 1) {
        ipad[i] = bkey[i] ^ 0x36363636; opad[i] = bkey[i] ^ 0x5c5c5c5c
    }
    hash = binlMD5(ipad.concat(rstr2binl(data)), 512 + data.length * 8); return binl2rstr(binlMD5(opad.concat(hash), 512 + 128))
}
function rstr2hex(input) {
    var hexTab = '0123456789abcdef'
    var output = ''
    var x
    var i
    for (i = 0; i < input.length; i += 1) {
        x = input.charCodeAt(i); output += hexTab.charAt((x >>> 4) & 0x0f) + hexTab.charAt(x & 0x0f)
    }
    return output
}
function str2rstrUTF8(input) {
    return unescape(encodeURIComponent(input))
}
function rawMD5(s) {
    return rstrMD5(str2rstrUTF8(s))
}
function hexMD5(s) {
    return rstr2hex(rawMD5(s))
}
function rawHMACMD5(k, d) {
    return rstrHMACMD5(str2rstrUTF8(k), str2rstrUTF8(d))
}
function hexHMACMD5(k, d) {
    return rstr2hex(rawHMACMD5(k, d))
}
function md5(string, key, raw) {
    if (!key) {
        if (!raw) {
            return hexMD5(string)
        }
        return rawMD5(string)
    }
    if (!raw) {
        return hexHMACMD5(key, string)
    }
    return rawHMACMD5(key, string)
}
function convertKeysToCamelCase(obj) {
    if (obj === null || typeof obj !== "object") {
        return obj;
    }

    if (Array.isArray(obj)) {
        return obj.map(item => convertKeysToCamelCase(item));
    }

    const camelCaseObj = {};
    for (const key in obj) {
        if (Object.prototype.hasOwnProperty.call(obj, key)) {
            const camelCaseKey = key.replace(/_([a-z])/g, function (match, letter) {
                return letter.toUpperCase();
            });
            camelCaseObj[camelCaseKey] = convertKeysToCamelCase(obj[key]);
        }
    }

    return camelCaseObj;
}

//任务并行控制器，第一个参数任务队列，第二个参数，并行数限制，第三个参数，所有任务执行完成后回调
class ConcurrencyControl {
    constructor(tasks, limit, callback) {
        this.tasks = tasks.slice() // 浅拷贝，避免修改原数据
        this.queue = new Set() // 任务队列
        this.limit = limit // 最大并发数
        this.callback = callback // 回调
        this.isStopped = false
    }
    stop() {
        this.isStopped = true
        this.tasks.length = 0
    }
    runTask() {
        if (this.isStopped) {
            return
        }
        if (this.tasks.length === 0 && this.queue.size === 0) {
            return
        }
        while (!this.isStopped && this.queue.size < this.limit && this.tasks.length > 0) {
            const task = this.tasks.shift()
            if (!task) break
            const p = task() // 生成 Promise
            this.queue.add(p)
            p.finally(() => {
                this.queue.delete(p)
                if (this.isStopped) {
                    return
                }
                if (this.tasks.length > 0) {
                    this.runTask() // 继续拉下一个
                } else if (this.queue.size === 0) {
                    this.callback() // 所有任务完成
                }
            })
        }
    }
    addTask(task) {
        // 同步添加任务
        this.tasks.push(task)
        // 当直接调用 addTask 也可直接执行
        this.runTask()
    }
}

function buildYandexVariants(data, currentOskuId) {

    // 图片补全 https:
    function formatImageUrl(url) {
        if (!url) return "";
        if (url.startsWith("//")) {
            return "https:" + url;
        }
        return url;
    }

    const groups = data.map(group => {
        return group.filterValues.map(item => ({
            Key: group.id,
            Value: item.fullTitle,
            VariantImageUrl: formatImageUrl(item.imageUrl),
            skuId: item.transition?.params?.oskuId || (item.isChecked ? currentOskuId : "")
        }));
    });

    function cartesian(arr) {
        return arr.reduce((acc, curr) => {
            const result = [];

            acc.forEach(a => {
                curr.forEach(c => {
                    result.push([...a, c]);
                });
            });

            return result;
        }, [[]]);
    }

    const combinations = cartesian(groups);

    // 转换成目标格式
    return combinations.map(items => {
        // 优先取当前组合中存在的图片
        const imageItem = items.find(x => x.VariantImageUrl);
        const skuItem = items.find(x => x.skuId);

        return {
            skuId: skuItem?.skuId || "",
            Property: items.map(x => ({
                Key: x.Key,
                Value: x.Value
            })),

            VariantImageUrl: imageItem?.VariantImageUrl || ""
        };
    });
}


function attachYandexSkuInfo(variants, skuData) {

    const skuMap = new Map(
        skuData.map(x => [String(x.skuId), x])
    );

    return variants.map(variant => {

        const skuInfo = skuMap.get(String(variant.skuId));
        if (!skuInfo) {
            //未匹配到SKU
            return variant;
        }

        return {
            ...variant,
            VariantImageUrl: skuInfo.images.join("|"),
            Price: skuInfo.price
        };
    });
}

function AnalyticalArkSwiftProducts(content, tab, souceUrl, funCallback) {
    if (content == "none")
        throw new Error("未能成功获取到数据源！若此错误频繁出现，请联系客服！");

    if (content.Data) {
        var model = {
            Html: JSON.stringify(content.Data),
            SourcePlatform: 59,
            SouceUrl: souceUrl
        };
        SaveLiknProduct(tab, model, funCallback);
        return;
    }

    var itemCode = "";
    var url = souceUrl.split("?")[0];
    if (url.indexOf("~") > -1) {
        itemCode = url.substring(url.lastIndexOf("~") + 1);
    }
    if (!itemCode) {
        throw new Error("未获取到商品Item Code");
    }

    var requestUrl = "https://www.arkswift.com/api/v1/rest/product-details?id=" + encodeURIComponent(itemCode);
    request(requestUrl, {
        responseType: "json",
        method: "GET"
    }).then(response => {
        if (response && response.code == 200 && response.data) {
            var model = {
                Html: JSON.stringify(response.data),
                SourcePlatform: 59,
                SouceUrl: souceUrl
            };
            SaveLiknProduct(tab, model, funCallback);
        } else {
            throw new Error("ArkSwift产品接口请求失败！");
        }
    }).catch(reason => {
        catchFuncallback(reason, funCallback)
    });
}
