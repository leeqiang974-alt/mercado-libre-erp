//执行产品采集逻辑
function ExecuteProductAcquisitionLogic(url, tab, isVerifyDuplicate, isLinkCollect) {
    try {
        var platformData = MatchingPlatform(url);
        if (url == "https://www.wish.com/") {
            sendMessageToContentScript({ "Type": "Alter", "MessageType": "error", "Message": '当前地址不支持产品采集' }, tab, function (response) { });
            return;
        }

        var platformId = platformData.PlatformId;
        var platformName = platformData.PlatformName;
        // if(platformId==27){ //onbuy
        //    if (url.indexOf("/?variant=") > -1) {
        //         url=url.split('?')[0];
        //      }
        // }
        if (platformId > 0) {
            sendMessageToContentScript({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": true }, tab, function (response) { });
            if (isVerifyDuplicate) {
                function ExecuteVerifyDuplicate(processedUrl)
                {
                    if (processedUrl && processedUrl.indexOf('jinritemai') > -1&& processedUrl.indexOf('goods_detail') > -1) {
                        const keepParams = ['id', 'origin_type', 'c_biz_combo', 'with_sec_did','h5_origin_type','use_link_command','from_link','entrance_info','utm_campaign'];
                        processedUrl=cleanURL(processedUrl, keepParams);
                    }
                    if (processedUrl.indexOf("mobile.yangkeduo.com") > -1 || processedUrl.indexOf("mobile.pinduoduo.com") > -1) {
                        processedUrl = getUrlWithGoodsId(processedUrl);
                    }

                    VerifyDuplicate(processedUrl,
                        function (parentSku) {
                            if (parentSku !== "" && parentSku != null) {
                                sendMessageToContentScript({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
                                sendMessageToContentScript({ "Type": "ConfirmAcquisition", "MessageType": "warning", "Message": "该产品在无忧易售已有采集记录，ParentSku:【" + parentSku + "】，是否继续采集？", "Url": processedUrl }, tab, function (response) { });
                            }
                            else {
                                sendMessageToContentScript({ "Type": "Get" + platformName + "Text", "MessageType": "", "Message": "", "isLinkCollect": isLinkCollect, "sourceUrl": processedUrl }, tab, function (response) {
                                    if (response !== null) {
                                        AnalyticalProducts(platformId, response, tab, processedUrl, sendMessageToContentScript);
                                    }
                                });
                            }
                        },
                        function (msg) {
                            sendMessageToContentScript({ "Type": "Alter", "MessageType": "error", "Message": msg }, tab, function (response) { });
                        }
                    );
                }

                //验证前对URL的特殊处理
                if (url.indexOf('dj.1688.com') != -1 || url.indexOf('http://detail.m.1688.com') != -1) {
                    request(url, {
                        method: "GET",
                        responseType: "text"
                    }).then(detailResult => {
                        if (detailResult && detailResult.indexOf('b2c_auction=') > -1) {
                            var offerId = detailResult.split('b2c_auction=')[1].split('&')[0];
                            url = 'https://detail.1688.com/offer/' + offerId + '.html';
                        }
                        ExecuteVerifyDuplicate(url);
                    }).catch(reason => {
                        ExecuteVerifyDuplicate(url);
                    });
                }
                else {
                    ExecuteVerifyDuplicate(url);
                }
            }
            else {
                sendMessageToContentScript({ "Type": "Get" + platformName + "Text", "MessageType": "", "Message": "", "isLinkCollect": isLinkCollect,"sourceUrl": url }, tab, function (response) {
                    if (response !== null) {
                        AnalyticalProducts(platformId, response, tab, url, sendMessageToContentScript);
                    }
                });
            }
        }
        else {
            throw new Error("当前地址：[" + url + "]暂不支持产品采集");
        }
    } catch (error) {
        chrome.notifications.create("51selling_tip" + new Date(), {
            type: 'basic',
            iconUrl: 'img/icon_128.png',
            title: '无忧易售产品采集',
            message: "产品采集失败！" + error.message
        });
    }
}

//匹配平台
function MatchingPlatform(url) {
    var platformId = 0;
    var platformName = '';
    var type = "detail";
    var isDetail=true;

    for (let i = 0; i < config.platformArr.length; i++) {
        const platform = config.platformArr[i];
        for (let j = 0; j < platform.MatchingURLs.length; j++) {
            const item = platform.MatchingURLs[j];

            if (item.indexOf('*') !== -1) {
                const itemUrls = item.split('*');

                let matched = true;
                for (let index = 0; index < itemUrls.length; index++) {
                    if (url.indexOf(itemUrls[index]) < 0) {
                        matched = false;
                        break;
                    }
                }

                if (matched) {
                    platformId = platform.PlatformId;
                    platformName = platform.PlatformName;
                    break;
                }
            } else if (url.indexOf(item) !== -1) {
                platformId = platform.PlatformId;
                platformName = platform.PlatformName;
                break;
            }
        }

        if (platformId > 0) {
            // 判断是明细页还是类目页面
            for (const item in platformLinkRule) {
                if (url.indexOf(item) !== -1) {
                    type = platformLinkRule[item].getType(url);
                    isDetail = platformLinkRule[item].detail(url);
                    break;
                }
            }
            break;
        }
    }
    return { "PlatformId": platformId, "PlatformName": platformName, "CrawlType": type,"isDetail":isDetail };
}
//验证是否登录
function VerifyLogin(successfulCallBack, failedCallBack) {

    chrome.cookies.get({ "url": config.url.domain(), "name": config.cookieName1 }, function (cookie) {
        if (cookie && cookie !== null && cookie.value !== undefined && cookie.value !== '') {
            chrome.cookies.get({ "url": config.url.domain(), "name": config.cookieName2 }, function (cookie2) {
                if (cookie2 && cookie2 !== null && cookie2.value !== undefined && cookie2.value !== '') {
                    successfulCallBack();
                }
                else {
                    failedCallBack();
                }
            });
        }
        else {
            failedCallBack();
        }
    });
}

//重复采集
function ExecuteRepeateProduct(url, tab,failedCallBack){
    var platformData = MatchingPlatform(url);
    var platformId = platformData.PlatformId;
    if(platformId>0){
        sendMessageToContentScript({ "Type": "RepeateCollect"}, tab, function (response) {
            if (response !== null) {
                ExecuteProductDetail(url,platformId, false, function(res){
                    failedCallBack(res);
                });
            }
        });
    }else{
      failedCallBack({MessageType:"error",Message:"当前url地址不支持采集"});
    }
}
//验证版本号
function VerifyVersion(successfulCallBack, failedCallBack) {
    successfulCallBack();

}
// 类目采集
function categoryCrawlProcess(platformId, platformName, url,tab, sendResponse) {
    VerifyLogin(function () {
        try {
            sendResponse('');
            sendMessageToContentScript({ "Type": "CheckCategoryBtnDisabled", "Disabled": true }, tab, function (response) { });
            sendMessageToContentScript({ "Type": platformName + "CategoryCrawl", "MessageType": "", "Message": "" }, tab, function (response) {
                if (response !== null) {
                    AnalyticalCategory(platformId, response, tab, sendMessageToContentScript);
                }
            });

        } catch (e) {
            sendMessageToContentScript({ "Type": "CheckCategoryBtnDisabled", "Disabled": false }, tab, function (response) { });
            chrome.notifications.create("51selling_tip" + new Date(), {
                type: 'basic',
                iconUrl: 'img/icon_128.png',
                title: '无忧易售产品采集',
                message: "类目采集失败！" + error.message
            });
        }
    }, function () {
        sendMessageToContentScript({ "Type": "RedirectSite", "MessageType": "warning", "Message": "当前无登录用户，点击确认前往登录！", "Site": "https://www.51selling.com/User/Login" }, tab, function (response) {

        });
    })
}

//根据获取符号获取对应货币简码
function GetcurrencyCode(price, defaultCode) {
    var currencyCode = "";
    if (defaultCode)
        currencyCode = defaultCode;
    if (price.indexOf("$") >= 0) {
        currencyCode = "USD";
    } else if (price.indexOf("₽") >= 0){
        currencyCode = "RUB";
    } else if (price.indexOf("BYN") >= 0) {
        currencyCode = "BYN";
    } else if (price.indexOf("₸") >= 0) {
        currencyCode = "KZT";
    } else if (price.indexOf("₪") >= 0) {
        currencyCode = "ILS";
    } else if (price.indexOf("֏") >= 0) {
        currencyCode = "AMD";
    } else if (price.indexOf("kr") >= 0) {
        currencyCode = "DKK";
    } else if (price.indexOf("C$") >= 0) {
        currencyCode = "CAD";
    } else if (price.indexOf("с") >= 0) {
        currencyCode = "KGS";
    } else if (price.indexOf("¥") >= 0) {
        currencyCode = "CNY";
    }
    return currencyCode;
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

//拼多多链接去除链接多余参数，保留goods_id
function getUrlWithGoodsId(urlStr) {
    const [baseUrl, queryString] = urlStr.split('?');  // 分离 URL 和参数部分
    if (!queryString) return urlStr;
    const queryParams = queryString.split('&');
    const goodsIdParam = queryParams.find(param => param.startsWith('goods_id='));  // 找到包含 goods_id 的参数
    if (!goodsIdParam) return baseUrl;    // 如果没有找到 goods_id，返回基础 URL
    return `${baseUrl}?${goodsIdParam}`;  // 返回只包含 goods_id 的 URL
}