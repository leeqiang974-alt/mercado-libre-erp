importScripts("js/config.js", "js/requestapi.js", "js/sendmessage.js", "js/callserver.js", "js/analyticalproducts.js", "js/productacquisition.js");
let main = chrome.runtime.getURL('html/main.html');
//监听来自外部扩展和网页的消息
chrome.runtime.onMessageExternal.addListener(function (request, sender, sendResponse) {
    // 存储数据 
    chrome.storage.local.set({ urls: request.urls }, function () {
    });
    chrome.tabs.create({ url: main }, function (mainTab) {
        chrome.storage.local.set({ _TabId: mainTab.id, urls: request.urls });
    });
});

// 进入mian.html
chrome.action.onClicked.addListener((tab) => {
    // 当扩展图标被点击时，这里的代码将被执行
    chrome.tabs.create({ url: "html/main.html" });
});

chrome.runtime.onInstalled.addListener(function () {
    //创建页面右键菜单
    chrome.contextMenus.create({
        type: 'normal',
        title: '采集此产品',
        id: '51Selling_CollectProductsMenu',
        contexts: ['all']
    }, function () {
    });
});


chrome.contextMenus.onClicked.addListener(function (info, tab) {
    GenericOnClick(info, tab);

});
var tabId = '';

// 监听来自content-script的消息
chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {
    tabId = request.tabId + '';
    if (request.Type === "CollectionGoods") {
        let itemUrl = sender.url;
        if (request.sourceUrl != null && request.sourceUrl !== '') {
            itemUrl = request.sourceUrl;
        }
        const specPlatform = ['yangkeduo.com'];
        if (specPlatform.find(x => sender.url.indexOf(x) > 0)) {
            itemUrl = sender.tab.url;
        }
        let isLinkCollect = false;
        if (request.link) {
            itemUrl = request.link;
            isLinkCollect = true;
        }
        GenericOnClick({ "pageUrl": itemUrl }, sender.tab, request.IsVerifyDuplicate, true, isLinkCollect);
        sendResponse('');
    } else if (request.Type === "UploadImage") {
        var imageUrl = request.ImageUrl;
        UploadImageToOss(imageUrl, sendResponse);
    } else if (request.Type === "VerifyVersion") {
        sendResponse('');
    } else if (request.Type === "CollectionCategory") {
        categoryCrawlProcess(request.PlatformId, request.PlatformName, sender.url, sender.tab, sendResponse);
    } else if (request.Type === "CollectionRepeatGoods") {
        ExecuteRepeateProduct(request.link, sender.tab, sendResponse)
    } else if (request.Type === "GetVersion") {
        const currentVersion = chrome.runtime.getManifest().version;

        // 异步处理获取版本号，120分钟缓存
        checkAndStoreLatestVersion(120).then(async () => {
            const localData = await chrome.storage.local.get(['latestStoredVersion']);
            const latestVersion = localData.latestStoredVersion;
            sendResponse({
                CurrentVersion: currentVersion,
                LatestVersion: latestVersion || currentVersion,
                NeedUpdate: latestVersion ? compareVersions(latestVersion, currentVersion) > 0 : false
            });
        }).catch(error => {
            sendResponse({
                CurrentVersion: currentVersion,
                LatestVersion: currentVersion,
                NeedUpdate: false
            });
        });
    } else if (request.Type === "GetMercadoHtmlByTab") {
        const requestUrl = request.RequestUrl;
        let createdTabId = null;
        let timeoutId = null;
        let hasResponded = false;

        const cleanup = function () {
            if (timeoutId) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }
            chrome.tabs.onUpdated.removeListener(handleUpdated);
            if (createdTabId) {
                chrome.tabs.remove(createdTabId, function () {
                    void chrome.runtime.lastError;
                });
                createdTabId = null;
            }
        };

        const finish = function (response) {
            if (hasResponded) {
                return;
            }
            hasResponded = true;
            cleanup();
            sendResponse(response);
        };

        const handleUpdated = function (tabId, changeInfo, tab) {
            if (tabId !== createdTabId || changeInfo.status !== 'complete') {
                return;
            }

            setTimeout(function () {
                chrome.tabs.sendMessage(createdTabId, { Type: "GetMercadoHtml", RequestUrl: requestUrl }, function (response) {
                    if (chrome.runtime.lastError) {
                        finish({ IsSuccess: false, Data: chrome.runtime.lastError.message });
                        return;
                    }

                    finish(response || { IsSuccess: false, Data: "Mercado page HTML was not returned" });
                });
            }, 1500);
        };

        chrome.tabs.onUpdated.addListener(handleUpdated);
        chrome.tabs.create({ url: requestUrl, active: false }, function (tab) {
            if (chrome.runtime.lastError || !tab || !tab.id) {
                cleanup();
                sendResponse({ IsSuccess: false, Data: chrome.runtime.lastError ? chrome.runtime.lastError.message : "Failed to create Mercado tab" });
                return;
            }

            createdTabId = tab.id;
            timeoutId = setTimeout(function () {
                finish({ IsSuccess: false, Data: "Mercado page load timed out" });
            }, 30000);
        });
    } else if (request.type === 'PROXY_FETCH') {
        const { url, options } = request.payload;
        fetch(url, options)
            .then(response => response.text())
            .then(data => {
                sendResponse({ success: true, data: data });
            })
            .catch(error => {
                sendResponse({ success: false, error: error.message });
            });
    }
    return true;
});

//监听系统通知后用户点击按钮
chrome.notifications.onButtonClicked.addListener((notificationId, buttonIndex) => {
    if (notificationId.indexOf("51selling_login") > -1 && buttonIndex === 0) {
        chrome.tabs.create({
            //url: 'https://www.51selling.com'
            url: config.url.domain()
        });
    } else if (notificationId.indexOf("51selling_update") > -1 && buttonIndex === 0) {
        chrome.tabs.create({
            url: 'https://www.51selling.com/HelpDocument/ShowHelpDocument/8'
        });
    }
});


//监听Shopee页面所有请求消息
chrome.webRequest.onBeforeSendHeaders.addListener(
    (function (details) {
        if ((-1 !== details.url.indexOf("shopee") || -1 !== details.url.indexOf("xiapibuy")) && details.requestHeaders && details.requestHeaders.length && details.tabId != -1) {
            var shopeeHeadersData = { shopeeHeaders: true };

            var requestHeaders = details.requestHeaders;

            for (var i = 0; i < requestHeaders.length; i++) {
                var header = requestHeaders[i];
                shopeeHeadersData[header.name] = header.value;

                // 判断是否为最后一个请求头
                if (i + 1 === requestHeaders.length) {
                    shopeeHeadersData['shopeeV4Url'] = details.url;
                    sendMessageToContentScript({
                        "Type": "SaveKey",
                        "Key": "_LiSellingShopeeSign_",
                        "Value": shopeeHeadersData
                    }, { "id": details.tabId }, function (response) {
                    });
                    break;
                }
            }

        }
    }),
    {
        urls: [
            "*://*/api/v4/item/get?*",
            "*://*/api/v4/search/search_items?*",
            "*://*/api/v4/pdp/get_pc?*"
        ]
    }, ["requestHeaders"]);

//监听Temu页面请求头
chrome.webRequest.onBeforeSendHeaders.addListener(
    (function (details) {
        var requestHeaders = details.requestHeaders,
            temuCrawlUrl = details.url,
            lastIndex = temuCrawlUrl ? temuCrawlUrl.lastIndexOf('/') : -1,
            apiName = lastIndex > -1 ? temuCrawlUrl.substr(lastIndex + 1) : '';

        if (requestHeaders && requestHeaders.length && apiName && apiName === 'render') {
            var temuHeadersData = { temuHeaders: true };

            //循环请求头
            for (var i = 0; i < requestHeaders.length; i++) {
                temuHeadersData[requestHeaders[i].name] = requestHeaders[i].value;//把value返回到前台页面，用来请求temu获取数据

                //判断是否为最后一个请求头
                if (i + 1 === requestHeaders.length) {
                    sendMessageToContentScript({
                        "Type": "SaveKey",
                        "Key": "_LiSellingTemuSign_",
                        "Value": temuHeadersData
                    }, { "id": details.tabId }, function (response) {
                    });
                }
            }
        }
    }),
    {
        urls: [
            "*://www.temu.com/*/api/oak/integration/*",
            "*://www.temu.com/api/oak/integration/*"
        ]
    }, ["requestHeaders"]);

// 监听所有发往 1688 的请求
chrome.webRequest.onBeforeRequest.addListener(
    (details) => {
        // 只处理目标接口
        const url = new URL(details.url);
        const apiParam = url.searchParams.get('api');
        if (apiParam !== 'mtop.alibaba.alisite.cbu.server.ModuleAsyncService' || !details.url.includes('h5/mtop.alibaba.alisite.cbu.server.moduleasyncservice/1.0/')) {
            return;
        }

        let requestBody = null;

        // 尝试从 request body 中获取数据（POST）
        if (details.requestBody && details.requestBody.formData) {
            // form-data 格式（较少见）
            const formData = details.requestBody.formData;
            if (formData.data) {
                requestBody = decodeURIComponent(formData.data[0]);
            }
        } else if (details.requestBody && details.requestBody.raw) {
            // raw 格式（通常是 application/x-www-form-urlencoded 或 JSON 字符串）
            const raw = details.requestBody.raw[0];
            const uint8Array = new Uint8Array(raw.bytes);
            requestBody = new TextDecoder().decode(uint8Array);
        }

        // 如果是 GET 请求，参数可能在 URL 中
        if (!requestBody && details.url.includes('data=')) {
            const url = new URL(details.url);
            requestBody = url.searchParams.get('data');
        }

        if (!requestBody) {
            return;
        }

        const outer = JSON.parse(requestBody);
        // 支持两种常见字段名：'data' 或 'params'
        let innerStr = outer.data || outer.params;

        if (!innerStr) {
            // 有些情况下整个 requestBody 就是 inner JSON 字符串
            innerStr = requestBody;
        }

        // 第二次解析：解析内部的 appdata
        const inner = JSON.parse(innerStr);

        const catId = inner.appdata?.catId;

        if (catId) {
            sendMessageToContentScript({
                "Type": "SaveKey",
                "Key": "_LiSelling1688CatId_",
                "Value": catId
            }, { "id": details.tabId }, function (response) {
            });
        }
    },
    { urls: ["*://h5api.m.1688.com/*"] },
    ["requestBody"]
);


//监听Joom页面请求头
chrome.webRequest.onBeforeSendHeaders.addListener(
    function (details) {
        const url = details.url;
        const requestHeaders = details.requestHeaders;
        if (!requestHeaders || requestHeaders.length === 0) {
            return;
        }
        // 只提取我们需要的三个头
        const neededHeaders = ['x-version', 'x-api-token', 'Authorization'];
        const extractedHeaders = { joomHeaders: true };
        for (let i = 0; i < requestHeaders.length; i++) {
            const headerName = requestHeaders[i].name;
            if (neededHeaders.includes(headerName)) {
                extractedHeaders[headerName] = requestHeaders[i].value;
            }
        }
        // 确保至少提取到了一个关键头（可选）
        if (Object.keys(extractedHeaders).length > 1) {
            sendMessageToContentScript(
                {
                    Type: "SaveKey",
                    Key: "_LiSellingJoomSign_",
                    Value: extractedHeaders
                },
                { id: details.tabId },
                function (response) { }
            );
        }
    },
    {
        urls: ["*://www.joom.com/api/1.1/products/*/contentList/get*",
            "*://www.joom.com/api/1.1/*"
        ]
    },
    ["requestHeaders"]
);


//监听Temu页面请求Body
chrome.webRequest.onBeforeRequest.addListener(
    (function (details) {
        var requestBody = details.requestBody,
            requestBodyType = 'formData';

        if (requestBody && (requestBody.formData && requestBody.formData.data || requestBody.raw)) {
            if (requestBody && requestBody.raw && !requestBody.formData)
                requestBodyType = 'raw';
            requestBody = requestBodyType === 'formData' ? requestBody.formData.data[0] : requestBody.raw[0].bytes;

            if (requestBodyType === 'raw') {
                requestBody = decodeURIComponent(String.fromCharCode.apply(null, new Uint8Array(requestBody)));
            }

            sendMessageToContentScript({
                "Type": "SaveKey",
                "Key": "_LiSellingTemuRequestData_",
                "Value": { 'url': details.url, 'data': requestBody, 'type': requestBodyType }
            }, { "id": details.tabId }, function (response) {
            });
        }
    }),
    {
        urls: [
            "*://www.temu.com/*/api/oak/integration/*",
            "*://www.temu.com/api/oak/integration/*"
        ]
    }, ["requestBody"]);

// 监听拼多多批发页面所有请求消息
chrome.webRequest.onBeforeSendHeaders.addListener(
    (function (details) {
        var PinDuoDuoHeadersData = { PinDuoDuoHeaders: true };

        var requestHeaders = details.requestHeaders;
        for (var i = 0; i < requestHeaders.length; i++) {
            var header = requestHeaders[i];
            PinDuoDuoHeadersData[header.name] = header.value;

            // 判断是否为最后一个请求头
            if (i + 1 === requestHeaders.length) {
                sendMessageToContentScript({
                    "Type": "SaveKey",
                    "Key": "_LiSellingPinDuoDuoSign_",
                    "Value": PinDuoDuoHeadersData
                }, { "id": details.tabId }, function (response) {
                });
                break;
            }
        }
    }),
    {
        urls: [
            "*://pifa.pinduoduo.com/pifa/goods/queryGoodsShareInfo*"
        ]
    }, ["requestHeaders"]);

chrome.webRequest.onBeforeRequest.addListener(function (details) {
    if (details.method === 'GET') {
        setTimeout(function () {
            sendMessageToContentScript({
                "Type": "SaveKey",
                "Key": "_LiSellingJDSign_",
                "Value": details.url
            }, { "id": details.tabId }, function (response) {
            });
        }, 1000);
    }
},
    {
        urls: [
            "*://api.m.jd.com/?appid=pc-item-soa*",
            "*://api.m.jd.com/description/channel?appid=i-item_fe*"
        ]
    },
    ["requestBody"]);
//监听天猫页面所有请求消息，隐藏验证码
chrome.webRequest.onHeadersReceived.addListener(function (details) {
    //如果当前请求地址上带有slide?字段，那么就是天猫的滑动条验证码事件触发
    if (details.url.indexOf('slide?') !== -1 ||
        details.url.indexOf('https://h5api.m.tmall.com/h5/mtop.taobao.pcdetail.data.get/1.0/_____tmd_____/page/mtoph5_close_iframe_page') !== -1 ||
        details.url.indexOf('https://item.taobao.com/item.htm/_____tmd_____/page/close_iframe_page') !== -1 ||
        (details.url.indexOf('https://item.taobao.com/item.htm/_____tmd_____/report') !== -1 && details.url.indexOf('setCookieSuccess') !== -1)
        || details.url.indexOf('newslidevalidate?') !== -1) {
        //隐藏验证码
        sendMessageToContentScript({ "Type": "HideTmallVerifyBox" }, { "id": details.tabId }, function (response) {
        });
    }

    if (details.url.indexOf('market.yandex.ru/product--') !== -1 || details.url.indexOf('market.yandex.ru/card') !== -1 || details.url.indexOf('market.yandex.ru/pr') !== -1) {
        //隐藏验证
        sendMessageToContentScript({ "Type": "HideYandexVerifyBox" }, { "id": details.tabId }, function (response) { });
    }
},
    {
        urls: [
            "*://h5api.m.tmall.com/h5/mtop.taobao.detail.getdesc/*", //天猫新版页面的滑动条验证监听
            "*://h5api.m.tmall.com/h5/mtop.taobao.pcdetail.data.get/*", //天猫新版页面的滑动条验证监听
            "*://h5api.m.tmall.hk/h5/mtop.taobao.pcdetail.data.get/*", //天猫新版页面的滑动条验证监听
            "*://detail.tmall.com/item_o.htm/_____tmd_____/slide*",//天猫旧版页面的滑动条验证监听
            "*://item.taobao.com/item.htm/_____tmd_____/slide*",//天猫旧版页面的滑动条验证监听
            "*://h5api.m.taobao.com/h5/mtop.taobao.detail.getdesc/*", //淘宝新版滑动条验证监听
            "*://h5api.m.taobao.com/h5/mtop.taobao.pcdetail.data.get/*", //淘宝新版页面的滑动条验证监听
            "*://h5api.m.taobao.hk/h5/mtop.taobao.pcdetail.data.get/*", //淘宝新版页面的滑动条验证监听
            "*://item.taobao.com/item.htm/_____tmd_____/slide*", //淘宝滑动条验证监听
            "*://market.yandex.ru/*"
        ]
    });

//cookie变更监听
chrome.cookies.onChanged.addListener((changeInfo) => {
    if (!changeInfo.removed && changeInfo.cookie) {
        if (changeInfo.cookie.name == '_m_h5_tk') {
            var value = changeInfo.cookie.value;
            if (value.indexOf('_') > -1)
                value = value.split('_')[0];

            //存储数据到本地
            if (value && value.length > 0) {
                if (changeInfo.cookie.domain == '.taobao.com') {
                    chrome.storage.local.set({ wyystaobaoh5tk: value }, function () { });
                } else if (changeInfo.cookie.domain == '.tmall.com') {
                    chrome.storage.local.set({ wyystmallh5tk: value }, function () { });
                } else if (changeInfo.cookie.domain == '.aliexpress.com') {
                    chrome.storage.local.set({ wyysaliexpressh5tk: value }, function () { });
                } else if (changeInfo.cookie.domain == '.aliexpress.ru') {
                    chrome.storage.local.set({ wyysaliexpressruh5tk: value }, function () { });
                }
            }
        } else if (changeInfo.cookie.name == 'aep_usuc_f') {
            var value = changeInfo.cookie.value;
            //存储数据到本地
            if (value && value.length > 0) {
                if (changeInfo.cookie.domain == '.aliexpress.com') {
                    chrome.storage.local.set({ wyysaliexpressh5aepusucf: value }, function () { });
                } else if (changeInfo.cookie.domain == '.aliexpress.ru') {
                    chrome.storage.local.set({ wyysaliexpressruh5aepusucf: value }, function () { });
                }
            }
        }
    }
});

// 监听浏览器启动事件
chrome.runtime.onStartup.addListener(() => {
    (async () => {
        await checkAndStoreLatestVersion(10);
    })();
});

// 监听插件安装/更新事件，作为补充保障
chrome.runtime.onInstalled.addListener(() => {
    (async () => {
        await checkAndStoreLatestVersion(10);
    })();
});

//上传图片到OSS
function UploadImageToOss(imageUrl, sendResponse) {
    VerifyLogin(
        function () {
            UploadImage(imageUrl, function (image) {
                sendResponse(image);
            });
        },
        function () {
            sendResponse(imageUrl);//这里没登录也不报错，直接返回原图URL
        }
    );
}

//采集产品点击事件
function GenericOnClick(info, tab, isVerifyDuplicate = true, isContent = false, isLinkCollect = false) {
    //isContent表示是否来源于Content，用于判断应该给什么类型的弹窗，右键点击采集的，有可能页面没有注入脚本，无法弹出自定义弹窗
    VerifyLogin(//验证是否登录
        function () {
            let fnBody;
            let url;
            if (info.linkUrl === undefined) {
                url = info.pageUrl;
            } else {
                url = info.linkUrl;
                isLinkCollect = true;
                let isSupportSite = false;
                let isSupportUrl = false;
                if (url.indexOf('aliexpress.us') !== -1) {
                    fnBody = platformLinkRule['aliexpress.com'].detail;
                    isSupportSite = true;
                    if (fnBody(url)) {
                        isSupportUrl = true;
                    }
                } else {
                    for (let item in platformLinkRule) {
                        if (url.indexOf(item) !== -1) {
                            fnBody = platformLinkRule[item].detail;
                            isSupportSite = true;
                            if (fnBody(url)) {
                                isSupportUrl = true;
                            }
                        }
                    }
                }

                if (!isSupportSite) {
                    sendMessageToContentScript({
                        "Type": "Alter",
                        "MessageType": "error",
                        "Message": "该平台暂不支持快速采集!"
                    }, tab, function (response) {
                    });
                    return;
                }
                if (!isSupportUrl) {
                    sendMessageToContentScript({
                        "Type": "Alter",
                        "MessageType": "error",
                        "Message": "该链接不支持采集!"
                    }, tab, function (response) {
                    });
                    return;
                }
            }
            ExecuteProductAcquisitionLogic(url, tab, isVerifyDuplicate, isLinkCollect);
        },
        function () {
            if (isContent) {
                sendMessageToContentScript({
                    "Type": "RedirectSite",
                    "MessageType": "warning",
                    "Message": "当前无登录用户，点击确认前往登录！",
                    //"Site": "https://www.51selling.com/User/Login"
                    "Site": config.url.domain() + "/User/Login"
                }, tab, function (response) {
                });
            } else {
                chrome.notifications.create("51selling_login" + new Date(), {
                    type: 'basic',
                    iconUrl: 'img/icon_128.png',
                    title: '无忧易售产品采集',
                    //message: "当前无登录用户，请先前往https://www.51selling.com/进行登录！",
                    message: "当前无登录用户，请先前往" + config.url.domain() + "进行登录！",
                    buttons: [{ title: "立即前往" }]
                });
            }
        }
    );
}

//检查存储最新版本
async function checkAndStoreLatestVersion(duration) {
    try {
        const now = Date.now();

        // 1. 获取本地存储的最新版本号和获取时间
        const localData = await chrome.storage.local.get(['latestStoredVersion', 'versionFetchTimestamp']);
        let latestStoredVersion = localData['latestStoredVersion'];
        const lastFetchTime = localData['versionFetchTimestamp'];

        // 2. 获取当前插件版本号
        const currentExtensionVersion = chrome.runtime.getManifest().version;
        if (latestStoredVersion
            && compareVersions(latestStoredVersion, currentExtensionVersion) > 0)
            return;

        if (lastFetchTime && (now - lastFetchTime) < duration * 60 * 1000)
            return;

        // 4. 向后端 API 发送 POST 请求
        const response = await fetch(config.url.getChromeExtensionVersion(), {
            method: 'POST', // 指定为POST请求
            headers: {
                'Content-Type': 'application/json',
            },
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        // 5. 解析响应 JSON
        const apiResponse = await response.json();

        // 6. 检查响应中的 IsSuccess 字段
        if (!apiResponse.IsSuccess) {
            throw new Error(`API returned an error: ${apiResponse.Message || 'Unknown error'}`);
        }

        // 7. 从 Data 字段中提取版本号
        const newLatestVersion = apiResponse.Data.Version;

        // 8. 将获取到的新版本号和当前时间戳存回本地存储
        await chrome.storage.local.set({
            'latestStoredVersion': newLatestVersion,
            'versionFetchTimestamp': now
        });
    } catch (error) {
    }
}

/**
 * 比较两个版本号字符串的辅助函数
 * @param {string} v1 - 第一个版本号，如 "1.2.3"
 * @param {string} v2 - 第二个版本号，如 "1.3.0"
 * @returns {number} - 如果 v1 < v2 返回负数，v1 > v2 返回正数，相等返回 0
 */
function compareVersions(v1, v2) {
    const parts1 = v1.split('.').map(Number);
    const parts2 = v2.split('.').map(Number);

    for (let i = 0; i < Math.max(parts1.length, parts2.length); i++) {
        const num1 = parts1[i] || 0; // 如果某部分不存在，默认为0
        const num2 = parts2[i] || 0;

        if (num1 < num2)
            return -1;
        if (num1 > num2)
            return 1;
    }
    return 0;
}

chrome.tabs.onUpdated.addListener(function (tabId, changeInfo, tab) {
    //console.log(tab.url)
    // 检查页面加载完成
    if (changeInfo.status === 'complete') {

        // 过滤特定域名、拼多多
        if (tab.url.includes('yangkeduo.com')) {

            // 登录页面
            if (tab.url.includes('mobile.yangkeduo.com/login.html') && tab.index == 0) {//ERP打开的小窗体，才去打开登录页面 
                chrome.tabs.create({
                    url: tab.url
                });
                sendMessageToContentScript(
                    {
                        "Type": "WindowOpenerPostMessage",
                        "Message": { "Type": "ErrorMsg", "Message": '拼多多账号未登录' }
                    },
                    tab, function (response) {

                    });
            }

            //// 获取拼多多下单后回传订单号
            //if (tab.url.includes('/transac_wechat_wapcallback.html')) {
            //    //debugger
            //    //console.log('pdd订单链接' + tab.url)
            //    sendMessageToContentScript(
            //        {
            //            "Type": "BacklinkOrderDownloadInfo",
            //            "Url": tab.url
            //        },
            //        tab, function (response) {
            //            chrome.tabs.remove(tab.Id,()=>{});
            //        });
            //}

            /*
            eot=1 获取拼多多用户名
            eot=2 获取拼多多产品信息
            eot=3 拼多多自动下单
            eot=4 获取拼多多订单信息 
            */
            //获取拼多多用户名 eot=1
            if (tab.url.includes('?eot=1')) {
                getPDDCookies('https://mobile.yangkeduo.com/', function (x, y) {
                    sendMessageToContentScript(
                        {
                            "Type": "GetPDDUserName",
                            "Data": x
                        },
                        tab, function (response) {

                        });
                });
            }

            //获取拼多多产品信息
            if (tab.url.includes('&eot=2') || ((tab.url.includes('goods2.html') || tab.url.includes('goods.html') || tab.url.includes('goods_id='))
                && !tab.url.includes('order_checkout.html') && !tab.url.includes('transac_wechat_wapcallback.html') && tab.index == 0)) {
                sendMessageToContentScript(
                    {
                        "Type": "GetPDDProductInfo",
                        "Data": tab.url
                    },
                    tab, function (response) {

                    });
            }

            // 拼多多自动下单
            if (tab.url.includes('&eot=3')) {
                sendMessageToContentScript(
                    {
                        "Type": "PDDOrderDownload",
                    },
                    tab, function (response) {

                    });
            }

            // 获取拼多多订单信息
            if (tab.url.includes('&eot=4') || (tab.url.includes('parent_order_sn=') && tab.index == 0)) {
                sendMessageToContentScript(
                    {
                        "Type": "GetPDDOrderInfo",
                    },
                    tab, function (response) {

                    });
            }

            // 获取拼多多订单列表
            if (tab.url.includes('&eot=5')) {
                sendMessageToContentScript(
                    {
                        "Type": "GetPDDOrderList",
                    },
                    tab, function (response) {

                    });
            }
        }

        if (tab.url.includes('wx.tenpay.com/cgi-bin/mmpayweb-bin/checkmweb?prepay_id=') && tab.index == 0) {
            chrome.tabs.remove(tab.Id, () => { });
            //sendMessageToContentScript(
            //{
            //    "Type": "WindowOpenerPostMessage",
            //    "Message": { "Type": "CloseWX", "Message": '关闭拼多多支付页面' }
            //},
            //tab, function (response) {

            //});
        }
    }
});


chrome.webRequest.onBeforeRequest.addListener(
    function (details) {
        // 检查是否是目标页面
        if (details.url.includes('yangkeduo.com') && details.url.includes('/transac_wechat_wapcallback.html')) {
            // 可选：发送消息给 content script 或 popup  
            sendMessageToContentScript(
                {
                    "Type": "BacklinkOrderDownloadInfo",
                    "Url": details.url
                },
                { "id": details.tabId }, function (response) {
                    chrome.tabs.remove(details.tabId, () => { });
                });
        }
    },
    { urls: ["https://*.yangkeduo.com/*"] },
    ["requestBody"]
);