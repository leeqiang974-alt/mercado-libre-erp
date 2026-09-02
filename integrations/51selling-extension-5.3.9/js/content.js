//监听backgroud的消息
NotificationList = []

chrome.runtime.onMessage.addListener(receiveMessages);

// 当文档加载完成时执行  
document.addEventListener('DOMContentLoaded', function () {
    //引入JS
    let jsArr = ["js/config.js", "js/requestapi.js", "js/sendmessage.js", "js/callserver.js", "js/analyticalproducts.js", "js/productacquisition.js", "js/pddorderdownload.js"];
    jsArr.forEach((item) => {
        let script = document.createElement('script');
        script.setAttribute('type', 'text/javascript');
        script.setAttribute('src', item);
        document.getElementsByTagName('head')[0].appendChild(script);
    });
    // 从本地存储中获取数据  
    chrome.storage.local.get('urls', function (result) {

        // 如果找到了数据  
        if (chrome.runtime.lastError) {
            console.error(chrome.runtime.lastError);
        } else {

            let datas = result.urls;
            let dataText = '';
            if (Array.isArray(datas)) {
                for (let data of datas) {
                    dataText += data + '\n'.trim();
                }
                dataText = dataText.slice(0, -'\n'.length);
            }
            // 找到页面上的文本元素并更新其内容  
            let textElement = document.getElementById('urlCollect');
            let urlBtn = document.getElementById('urlCollectBtn');
            if (textElement) {
                textElement.textContent = dataText;
                if (dataText && dataText.length > 0) {
                    //触发点击事件
                    urlBtn.click();
                }

                //清除本地缓存
                chrome.storage.local.remove(["urls"], function () { });
            }
        }
    });
});

//亚马逊并发调用接口获取变体数据
async function executeRequestsInBatches(dimensionToAsinMap, request, batchSize = 10) {
    const objArr = []; // 存储所有请求的结果
    const entries = Object.entries(dimensionToAsinMap); // 获取 dimensionToAsinMap 的键值对数组

    // 遍历所有的键值对，按照批次执行
    for (let i = 0; i < entries.length; i += batchSize) {
        // 每次取出 batchSize 个元素作为一批请求
        const batch = entries.slice(i, i + batchSize);

        // 将这一批请求并发执行
        const promises = batch.map(([key, value]) => {
            // 构造新的 URL
            let newUrl = request.SouceUrl;
            try {
                const url = new URL(request.SouceUrl);
                newUrl = `${url.origin}/dp/${value}`;
            } catch (e) {
                newUrl = request.SouceUrl.replace(/\/[A-Z0-9]{10}(?=\/|\?|$)/, `/${value}`);
            }

            // 返回一个新的 Promise 进行 AJAX 请求
            return new Promise((resolve, reject) => {
                try {
                    $.ajax({
                        url: newUrl,
                        method: 'GET',
                        async: true, // 异步请求
                        success: function (html) {

                            console.log('html', html);

                            // 创建 DOMParser 实例
                            const parser = new DOMParser();
                            // 解析 HTML 字符串
                            const doc = parser.parseFromString(html, 'text/html');

                            //当前变体图片数据
                            let imgArr = [];
                            try {
                                const scripts = Array.from(doc.querySelectorAll('script'));

                                const targetScript = scripts.find(s => {
                                    const txt = s.textContent || '';
                                    return txt.includes('ImageBlockATF')
                                        && txt.includes('colorImages')
                                        && txt.includes('initial');
                                });

                                if (!targetScript) {
                                    console.warn('未找到目标 script');
                                    return null;
                                }

                                // 3. 提取 var data = { ... };
                                const scriptText = targetScript.textContent;

                                // 使用非贪婪匹配，匹配到第一个 };
                                const match = scriptText.match(/var\s+data\s*=\s*({[\s\S]*?});/);

                                if (!match) {
                                    console.warn('未匹配到 data 对象');
                                    return null;
                                }

                                let dataStr = match[1].toString();

                                // 1. 去掉 Date.now()
                                dataStr = dataStr.replace(/Date\.now\(\)/g, '0');

                                // 2. 单引号 → 双引号（key 和 value）
                                dataStr = dataStr.replace(/'/g, '"');

                                // 3. 去掉尾逗号
                                dataStr = dataStr.replace(/,\s*([}\]])/g, '$1');

                                try {
                                    let imgDataObj = JSON.parse(dataStr);

                                    imgArr = imgDataObj.colorImages.initial.map(item =>
                                        item.hiRes ? item.hiRes : item.large
                                    );
                                } catch (e) {
                                    var imgDataObj = extractColorImagesInitial(dataStr);

                                    imgArr = imgDataObj.map(item =>
                                        item.hiRes ? item.hiRes : item.large
                                    );
                                }

                                let b = 1;
                            } catch (e) {
                                console.error('JSON 解析失败', e);
                            }

                            // 初始化价格变量
                            let Price = "0";
                            let Size = "";
                            let Color = "";

                            // 查找价格信息
                            let priceDiv = doc.getElementById('corePriceDisplay_desktop_feature_div');
                            let priceSpan = priceDiv?.querySelector('span.a-price-whole');
                            if (priceSpan) {
                                let allPrice = priceSpan.textContent.replace(/[^0-9]/g, '');
                                let fractionPriceSpan = priceDiv.querySelector('.a-price-fraction');
                                if (fractionPriceSpan) {
                                    allPrice = allPrice + "." + fractionPriceSpan.textContent;
                                }
                                Price = allPrice;
                            } else {
                                let priceDiv2 = doc.getElementById('corePrice_desktop');
                                let priceSpan2 = priceDiv2.querySelector('.a-offscreen');
                                if (priceSpan2) {
                                    Price = priceSpan2.textContent;
                                }
                            }

                            let twisterContainerDiv = doc.getElementById('twisterContainer');
                            if (twisterContainerDiv) {
                                var sizeDom = twisterContainerDiv.querySelector('.a-dropdown-prompt');
                                if (sizeDom) {
                                    Size = sizeDom.textContent
                                } else {
                                    console.log('尺码未找到');
                                }
                            } else {
                                console.log('尺码未找到');
                            }

                            let colorDiv = doc.getElementById('variation_color_name');
                            if (colorDiv) {
                                let colorSpan = colorDiv?.querySelector('.selection');
                                if (colorSpan) {
                                    Color = colorSpan.textContent.trim();
                                } else {
                                    console.log('颜色未找到');
                                }
                            } else {
                                console.log('颜色未找到');
                            }

                            let dataObj = {
                                Price,
                                Size,
                                Color,
                                Id: value,
                                Imgs: imgArr
                            }
                            objArr.push(dataObj)

                            resolve(); // 请求成功后调用 resolve
                        },
                        error: function (jqXHR, textStatus, errorThrown) {
                            console.error(`Error fetching ${newUrl}:`, textStatus, errorThrown);
                            reject(new Error(`Error fetching ${newUrl}: ${textStatus}`)); // 请求失败后调用 reject
                        }
                    });
                } catch (e) {

                }
            });
        });

        // 使用 await 等待这一批的所有请求完成
        await Promise.all(promises);
    }

    function extractColorImagesInitial(scriptText) {
        if (!scriptText) return [];

        const key = '"colorImages"';
        const idx = scriptText.indexOf(key);
        if (idx === -1) return [];

        // 找到 initial 后的第一个 [
        const initialIdx = scriptText.indexOf('"initial"', idx);
        if (initialIdx === -1) return [];

        const arrayStart = scriptText.indexOf('[', initialIdx);
        if (arrayStart === -1) return [];

        let i = arrayStart;
        let depth = 0;
        let inString = false;
        let escaped = false;

        for (; i < scriptText.length; i++) {
            const ch = scriptText[i];

            // 字符串状态处理
            if (inString) {
                if (escaped) {
                    escaped = false;
                } else if (ch === '\\') {
                    escaped = true;
                } else if (ch === '"') {
                    inString = false;
                }
                continue;
            } else {
                if (ch === '"') {
                    inString = true;
                    continue;
                }
            }

            if (ch === '[') depth++;
            if (ch === ']') depth--;

            if (depth === 0) {
                // i 是数组结尾 ]
                const jsonArrayStr = scriptText.slice(arrayStart, i + 1);
                try {
                    return JSON.parse(jsonArrayStr);
                } catch (e) {
                    console.error("JSON.parse 失败", e);
                    return [];
                }
            }
        }

        return [];
    }

    //将当前页面显示的变体挪到数据第一个位置
    const targetIndex = objArr.findIndex(item => {
        return item.Id && typeof item.Id === 'string' && document.URL.includes(item.Id);
    });
    if (targetIndex !== -1 && targetIndex > 0) {
        const movedItem = objArr.splice(targetIndex, 1)[0];
        objArr.unshift(movedItem);
    }

    // 所有请求完成后，返回 objArr
    return objArr;
}



//从eBay页面中获取数据
function getEbayPageData(doc) {
    var scripts = doc.querySelectorAll("script");
    var productJs = "";
    var scriptKeyword = "$MC=(window.$MC||[]).concat(";

    // 获取商品数据
    for (var i = 0; i < scripts.length; i++) {
        var script = scripts[i];
        if (script.innerHTML.indexOf(scriptKeyword) > -1) {
            productJs = script.innerHTML.split(scriptKeyword)[1].slice(0, -1);
            break;
        }
    }

    // 补偿机制1
    if (productJs == "") {
        for (var i = 0; i < scripts.length; i++) {
            var script = scripts[i];
            if (script.innerHTML.indexOf('$96613636_C=(window.$96613636_C||[]).concat(') > -1) {
                productJs = script.innerHTML.split("||[]).concat(")[1].slice(0, -1);
                break;
            }
        }
    }

    // 补偿机制2
    if (productJs == "") {
        for (var i = 0; i < scripts.length; i++) {
            var script = scripts[i];
            if (script.innerHTML.indexOf('$M_96613636_C=(window.$M_96613636_C||[]).concat(') > -1) {
                productJs = script.innerHTML.split("$M_96613636_C=(window.$M_96613636_C||[]).concat(")[1].slice(0, -1);
                break;
            }
        }
    }

    // 补偿机制3
    if (productJs == "") {
        for (var i = 0; i < scripts.length; i++) {
            var script = scripts[i];
            if (script.innerHTML.indexOf('||[]).concat(') > -1 &&
                script.innerHTML.indexOf('model') > -1 &&
                script.innerHTML.indexOf('modules') > -1) {
                productJs = script.innerHTML.split("||[]).concat(")[1].slice(0, -1);
                break;
            }
        }
    }

    if (!productJs)
        return {};

    // 解析商品数据
    var productData = null;
    try {
        var data = JSON.parse(productJs);
        productData = data?.o?.w || null;
    } catch (e) {
        console.error("eBay productData解析失败", e);
        return {};
    }

    if (!productData)
        return {};

    // 获取分类
    var breadCrumbs = $(doc).find(".breadcrumbs").first().find("ul").children();
    var categoryName = '';
    if (breadCrumbs.length > 0) {
        categoryName = breadCrumbs[breadCrumbs.length - 1].innerText;
    }

    // 获取描述地址
    var htmldesurl = '';
    var descIframe = doc.getElementById('desc_ifr');
    if (descIframe)
        htmldesurl = descIframe.src;

    // 获取ItemId
    var itemId = "";
    try {
        itemId = doc.querySelector('div.tabs__content div.ux-layout-section__row span.ux-textspans.ux-textspans--BOLD')?.textContent || '';
    } catch (e) { }

    return {
        "htmldesurl": htmldesurl,
        "productData": productData,
        "categoryName": categoryName,
        "itemId": itemId
    };
}

function cleanHtmlKeepTags(htmlStr) {
    let doc = new DOMParser().parseFromString(htmlStr, "text/html");

    // 删除所有 <script> 和 <style>
    doc.querySelectorAll("script, style").forEach(el => el.remove());

    // 删除所有注释节点
    let walker = doc.createTreeWalker(doc.body, NodeFilter.SHOW_COMMENT, null, false);
    let commentNodes = [];
    while (walker.nextNode()) {
        commentNodes.push(walker.currentNode);
    }
    commentNodes.forEach(node => node.remove());

    // 遍历所有元素
    doc.body.querySelectorAll("*").forEach(el => {
        const tag = el.tagName.toLowerCase();

        if (["p", "br", "img"].includes(tag)) {
            // <img> 只保留 src 和 alt
            if (tag === "img") {
                let src = el.getAttribute("src");
                let alt = el.getAttribute("alt") || "";
                el.getAttributeNames().forEach(attr => el.removeAttribute(attr));
                if (src) el.setAttribute("src", src);
                if (alt) el.setAttribute("alt", alt);
            }
        } else if (tag === "li") {
            // li → 内容 + 换行
            el.replaceWith(...el.childNodes, doc.createTextNode("\n"));
        } else {
            // 其他标签 → 直接展开
            el.replaceWith(...el.childNodes);
        }
    });

    return doc.body.innerHTML.replace(/\n{2,}/g, "\n");
}

function receiveMessages(request, sender, sendResponse) {
    {
        if (request.Type === 'GetWishText') {
            let path = window.location.pathname.substring(window.location.pathname.indexOf('/product'));
            url = window.location.protocol + '//' + window.location.host + path;
            if (request.isLinkCollect) {
                url = request.sourceUrl;
            }

            sendResponse({ "isLinkCollect": true, "cookies": document.cookie, "url": url });
        } else if (request.Type === 'GetAliexpressText') {
            let boxObj = {};
            //笛卡尔积
            function cartesianProduct(input) {
                // 提取所有属性的值
                const keys = input.map(item => item.key);
                const values = input.map(item => item.values);

                // 递归计算笛卡尔积
                function calculateCartesian(arr) {
                    return arr.reduce((acc, current) => {
                        return acc.flatMap(x => current.map(y => [...x, y]));
                    }, [[]]);
                }

                // 计算所有组合
                const combinations = calculateCartesian(values);

                // 将组合转换为目标格式
                const result = combinations.map(combination => {
                    // 找到第一个有 imgUrl 的属性作为 VariantImageUrl
                    const variantImageUrl = combination.find(item => item.imgUrl)?.imgUrl || "";

                    // 构建 Property 数组
                    const property = combination.map((item, index) => ({
                        Key: keys[index],
                        Value: item.key
                    }));

                    return {
                        VariantImageUrl: variantImageUrl,
                        Property: property
                    };
                });

                return result;
            }
            //提取价格
            function extractNumbersAndSingleDot(str) {
                if (request.sourceUrl.indexOf("pl.aliexpress.com") > -1)
                    str = str.replace(",", ".");

                // 提取数字和第一个小数点
                const result = str.replace(/[^0-9.]/g, '');
                const firstDotIndex = result.indexOf('.');

                // 如果存在小数点，只保留第一个
                if (firstDotIndex !== -1) {
                    return result.slice(0, firstDotIndex + 1) + result.slice(firstDotIndex + 1).replace(/\./g, '');
                }

                return result;
            }
            try {
                //&& request.sourceUrl.indexOf("www.aliexpress.com") < 0 && request.sourceUrl.indexOf("www.aliexpress.us") < 0 
                if (document.getElementById("root")) {
                    let pageHtmlStr = document.getElementById("root").innerHTML;
                    let dom = new DOMParser();
                    let doc = dom.parseFromString(pageHtmlStr, 'text/html');

                    let Title = doc.querySelector('h1[data-pl="product-title"]')?.textContent.trim() || ''; //产品标题
                    if (!Title) {
                        Title = doc.querySelector('div[class^="title--wrap"] h1')?.textContent.trim() || '';
                    }
                    let VideoUrl = doc.querySelector('div[class^="video--wrap"] source')?.getAttribute('src') || ''; //产品视频

                    let DetailedDescription = doc.querySelector('div.detailmodule_html')?.innerHTML.trim() || ''; //产品富文本描述
                    let BriefDescription = "";  //产品文字描述
                    let ImageUrl = [];  //产品图片
                    let Price = 0; //产品价格
                    let PriceStr = doc.querySelector('div.price--current--I3Zeidd')?.textContent.trim();
                    if (!PriceStr) {
                        PriceStr = doc.querySelector('div[class^="price-default--wrap"]')?.textContent.trim()
                    }

                    if (PriceStr)
                        PriceStr = extractNumbersAndSingleDot(PriceStr);
                    Price = parseFloat(PriceStr);

                    let pdpInfoDiv = doc.querySelector('.pdp-info-left');
                    if (pdpInfoDiv) {
                        pdpImageUrls = Array.from(pdpInfoDiv.querySelectorAll('img'))
                            .map(img => img.getAttribute('src'))
                            .filter(src => src); // 过滤掉 null 或空值

                        ImageUrl.push(...pdpImageUrls);
                    }

                    let Parameters = []; //产品属性
                    let specificationList = doc.querySelector('[class^="specification--list"]');
                    if (specificationList) {
                        let props = specificationList.querySelectorAll('[class^="specification--prop"]');

                        props.forEach(prop => {
                            let key = prop.querySelector('[class^="specification--title"] span')?.textContent.trim();
                            let value = prop.querySelector('[class^="specification--desc"] span')?.textContent.trim();

                            if (key && value) {
                                Parameters.push({ "Key": key, "Value": value });
                            }
                        });
                    }

                    ///////////

                    // 1. 获取变体属性的名称
                    let variants = [];
                    let propertyNames = [];
                    let porpList = [];

                    doc.querySelectorAll('.sku-item--property--HuasaIz').forEach((propertyDiv) => {
                        let porpTitle = propertyDiv.querySelector('.sku-item--title--Z0HLO87')?.textContent.trim() || "";
                        porpTitle = porpTitle.split(":")[0].trim().replace(/\([^()]*\)/g, '');;

                        propertyNames.push(porpTitle)

                        let porpValueArr = [];
                        // 2. 遍历 skus 的 div
                        propertyDiv.querySelectorAll('.sku-item--skus--StEhULs > div').forEach((skuDiv) => {
                            let img = skuDiv.querySelector('img'); // 获取 img 标签
                            if (img) {
                                let porpAlt = img.alt.trim();
                                let porpImgUrl = img.src.trim();
                                let porpValue = {
                                    "key": porpAlt,
                                    "imgUrl": porpImgUrl
                                }
                                porpValueArr.push(porpValue);
                            } else {
                                let porpAlt = skuDiv.textContent.trim();
                                let porpValue = {
                                    "key": porpAlt,
                                    "imgUrl": ""
                                }
                                porpValueArr.push(porpValue);
                            }
                        });

                        let porpObj = {
                            "key": porpTitle,
                            "values": porpValueArr
                        }
                        porpList.push(porpObj);
                    });
                    variants = cartesianProduct(porpList);

                    variants.forEach(item => {
                        item.Property = JSON.stringify(item.Property);
                        item.Price = Price;
                        let jpgIndex = item.VariantImageUrl.indexOf(".jpg");
                        if (jpgIndex !== -1) {
                            item.VariantImageUrl = item.VariantImageUrl.slice(0, jpgIndex + 4); // +4 是为了包含 .jpg
                        }
                        if (ImageUrl.indexOf(item.VariantImageUrl) < 0) {
                            ImageUrl.push(item.VariantImageUrl);
                        }
                    });

                    if (doc.querySelector('div.detailmodule_html')) {
                        let detailModuleDiv = doc.querySelector('div.detailmodule_html');
                        BriefDescription = detailModuleDiv?.textContent.trim() || '';
                        // 提取 div 中的所有 img 标签的 src 并存入数组
                        let descImageUrls = Array.from(detailModuleDiv?.querySelectorAll('img') || [])
                            .map(img => img.getAttribute('src'))
                            .filter(src => src); // 过滤掉 null 或空值

                        ImageUrl.push(...descImageUrls);
                    }
                    for (var i = 0; i < ImageUrl.length; i++) {
                        let jpgIndex = ImageUrl[i].indexOf(".jpg");
                        if (jpgIndex !== -1) {
                            ImageUrl[i] = ImageUrl[i].slice(0, jpgIndex + 4); // +4 是为了包含 .jpg
                        }
                    }

                    let boxInfo = {
                        "Title": Title,
                        "DetailedDescription": btoa(encodeURI(DetailedDescription)),
                        "BriefDescription": BriefDescription,
                        "ImageUrl": ImageUrl.join("|"),
                        "PropertyName": propertyNames.length > 0 ? JSON.stringify(propertyNames) : "[]",
                        "SourceUrl": request.sourceUrl,
                        "VideoUrl": VideoUrl,
                        "IsClaimed": false,
                        "SourcePlatform": 3,
                        "Tags": [],
                        "Remark": "",
                        "CreateTime": "1900-01-01 00:00:00",
                        "Parameters": JSON.stringify(Parameters)
                    };

                    boxObj =
                    {
                        boxInfo,
                        variants
                    }
                    sendResponse(
                        {
                            "isLinkCollect": request.isLinkCollect,
                            "box": boxObj
                        }
                    );
                    console.log(boxObj);
                } else {
                    sendResponse({ "isLinkCollect": request.isLinkCollect });
                }
            } catch (e) {
                sendResponse({ "isLinkCollect": request.isLinkCollect });
            }
            return true;
        } else if (request.Type === 'GetBanggoodText') {
            sendResponse({ "isLinkCollect": request.isLinkCollect });
            return true;
        } else if (request.Type === "GetWalmartText") {
            sendResponse({ "isLinkCollect": request.isLinkCollect });
            return true;
        } else if (request.Type === 'GetTemuText') {
            let docType = 'type_0_type';
            if (window._LiSellingTemuSign_ !== undefined && window._LiSellingTemuRequestData_ !== undefined) {
                docType = 'type_1_type';
                let ajaxData = null;
                if (window._LiSellingTemuRequestData_.data) {//获取请求参数
                    try {
                        ajaxData = typeof window._LiSellingTemuRequestData_.data === 'string' ? JSON.parse(window._LiSellingTemuRequestData_.data) : window._LiSellingTemuRequestData_.data;
                    } catch (e) {
                        ajaxData = null;
                    }
                }

                let jsondata = "none";
                $.ajax({
                    type: 'POST',
                    headers: window._LiSellingTemuSign_,
                    withCredentials: true,
                    url: window._LiSellingTemuRequestData_.url,
                    async: false,
                    contentType: 'application/json',
                    dataType: 'json',
                    data: JSON.stringify(ajaxData),
                    success: function (results) {
                        //把得到的数据放到html字段里面
                        results.DocType = docType;
                        jsondata = JSON.stringify(results);
                    },
                    error: function () {
                    }
                });
                sendResponse({ "isLinkCollect": request.isLinkCollect, "DocType": docType, "Ext": jsondata });
            } else {
                sendResponse({
                    "isLinkCollect": request.isLinkCollect,
                    "DocType": docType,
                    "Ext": document.documentElement.outerHTML
                });
            }

            return true;
        } else if (request.Type === 'GetAliexpressRusText') {
            sendResponse({ "isLinkCollect": request.isLinkCollect });
            return true;
        } else if (request.Type === 'GetAmazonText') {

            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetJF91Text') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetAlibabaText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetAlibabaInternationText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetJoomText') {

            //变体属性
            let publicAttributeKeys = [];

            //标题
            let title = document.querySelector('.root___e0mAF').innerText;

            //价格
            let price = 0;
            const priceDoc1 = document.querySelector('.specialPrice____PiZ0');
            if (priceDoc1)
                price = extractPrice(priceDoc1.innerText);

            const priceDoc2 = document.querySelector('.price___Y4B7f');
            if (!priceDoc1 && priceDoc2)
                price = extractPrice(priceDoc2.innerText);

            //取出文本中的价格
            function extractPrice(text) {
                if (!text) return 0;
                const regex = /\d{1,3}(?:,\d{3})*(?:\.\d+)?/;
                const match = text.match(regex);
                return match ? Number(match[0].replace(/,/g, '')) : 0;
            }

            //产品图片
            const thumbsContainer = document.querySelector('.thumbs___hXThY');
            const imgElements = thumbsContainer.querySelectorAll('img');
            const productImgs = Array.from(imgElements).map(img => img.src.replace(/(_\d+_\d+)(\.\w+)$/, '_original$2'));

            //属性
            const items = document.querySelectorAll('.item___eCR3y');
            const params = [];
            items.forEach(item => {
                const key = item.querySelector('.name___c9ONu span')?.innerText.trim();
                const value = item.querySelector('.value___omEBd span')?.innerText.trim();
                if (key && value) {
                    params.push({
                        "Key": key,
                        "Value": value
                    });
                }
            });

            //富文本描述
            let detailedDesc = "";
            let detailedDescDoc = document.querySelector('.description___Wi2sH');
            if (detailedDescDoc)
                detailedDesc = detailedDescDoc.innerHTML.trim();

            //文本描述
            const paragraphs = document.querySelectorAll('.description___Wi2sH .paragraph___wH2O0');
            const briefDesc = Array.from(paragraphs)
                .map(p => p.innerText.trim())
                .join('\n');

            //变体
            //生成变体数据
            function processDataAndFillKeys() {
                const variantsContainer = document.querySelector('.variants___n9U3A');
                if (!variantsContainer) {
                    console.warn("未找到变体容器 .variants___n9U3A");
                    publicAttributeKeys = [];
                    return [];
                }

                // 获取所有变体选项块 (例如：Color块, Size块)
                const attributeSelectors = variantsContainer.querySelectorAll('.attributeSelector___Ac1zh');

                console.log(`找到 ${attributeSelectors.length} 个属性块 (例如颜色、尺寸等)`); // 调试日志

                const propertiesForCalculation = [];
                publicAttributeKeys = [];

                // --- 第一步：解析 DOM 提取数据 ---
                attributeSelectors.forEach((selector, index) => {
                    // 1. 提取属性名 (Key)
                    const keyElement = selector.querySelector('.headerTitle___DCgkh h2');
                    const key = keyElement ? keyElement.innerText.trim() : `属性${index + 1}`;

                    publicAttributeKeys.push(key);

                    // 2. 提取属性值 (Values)
                    const items = selector.querySelectorAll('.contentList___DwHzQ .item___FqPfz');
                    const values = [];

                    items.forEach((item, itemIndex) => {
                        const input = item.querySelector('input[type="radio"]');
                        if (input) {
                            let displayValue = input.value; // 兜底值：input 的 value
                            let imageUrl = '';

                            // --- 核心修改：更健壮的查找逻辑 ---

                            // 策略 A: 查找特定标题类名 (旧逻辑兼容)
                            const titleSpan = item.querySelector('.cardPickerTitle___aOpmp');
                            if (titleSpan && titleSpan.textContent.trim() !== '') {
                                displayValue = titleSpan.textContent.trim();
                            }
                            // 策略 B: 查找 Label 文本 (适配你提供的 HTML: .label___Luj9o > span)
                            else {
                                const labelSpan = item.querySelector('.label___Luj9o span');
                                if (labelSpan) {
                                    displayValue = labelSpan.innerText.trim();
                                }
                                // 策略 C: 如果上面都没找到，直接使用 input 的 value 属性 (最稳妥的兜底)
                                // 你的 HTML 中 input 有 value="L"，这能保证一定有值
                            }

                            // 获取图片 (如果有)
                            const img = item.querySelector('img');
                            if (img) {
                                imageUrl = img.src;
                            }

                            values.push({
                                value: displayValue,
                                imageUrl: imageUrl
                            });
                        }
                    });

                    // 只有当找到有效值时才加入数组，防止空属性导致计算错误
                    if (values.length > 0) {
                        propertiesForCalculation.push({
                            key: key,
                            values: values
                        });
                        console.log(`属性 [${key}] 提取到值:`, values.map(v => v.value)); // 调试日志
                    } else {
                        console.warn(`属性 [${key}] 未提取到任何值，已跳过`);
                    }
                });

                // --- 第二步：笛卡尔积生成组合 ---
                function cartesianProduct(arr) {
                    return arr.reduce((a, b) => {
                        return a.map(x => b.map(y => x.concat([y]))).reduce((a, b) => a.concat(b), []);
                    }, [[]]);
                }

                if (propertiesForCalculation.length === 0) {
                    console.warn("没有提取到任何属性数据");
                    return [];
                }

                const valuesForCartesian = propertiesForCalculation.map(p => p.values);
                const combinations = cartesianProduct(valuesForCartesian);

                console.log("生成的组合数量:", combinations.length); // 调试日志

                const result = combinations.map(combo => {
                    const propertyList = [];
                    let mainImageUrl = "";

                    combo.forEach((valObj, index) => {
                        propertyList.push({
                            "Key": propertiesForCalculation[index].key,
                            "Value": valObj.value
                        });

                        if (!mainImageUrl && valObj.imageUrl) {
                            mainImageUrl = valObj.imageUrl;
                        }
                    });

                    return {
                        "VariantImageUrl": mainImageUrl,
                        "Property": propertyList
                    };
                });

                return result;
            }

            // 3. 后处理：单属性分组编号逻辑
            function handleSingleAttributeVariants(data, keys) {
                // 只有单属性时处理
                if (keys.length !== 1) return data;

                const targetKey = keys[0];
                // 1. 创建一个Map来存储每个"原始值"对应的所有变体
                const groups = new Map();

                data.forEach(variant => {
                    const value = variant.Property.find(p => p.Key === targetKey)?.Value || "Unknown";
                    if (!groups.has(value)) {
                        groups.set(value, []);
                    }
                    groups.get(value).push(variant);
                });

                // 2. 重构数组：遍历每个分组，给组内的变体加上序号
                const result = [];

                for (let [originalValue, variants] of groups) {
                    // 如果这个组只有一个变体，且值不是 "Matches the image"，则不加序号
                    if (variants.length === 1 && originalValue !== "Matches the image") {
                        result.push(JSON.parse(JSON.stringify(variants[0])));
                    } else {
                        // 否则（组内有多个变体，或者虽然是单个但值是 "Matches the image"），都加序号
                        variants.forEach((variant, index) => {
                            const newVariant = JSON.parse(JSON.stringify(variant));
                            const property = newVariant.Property.find(p => p.Key === targetKey);
                            if (property) {
                                property.Value = `${originalValue}-${index + 1}`;
                            }
                            result.push(newVariant);
                        });
                    }
                }

                return result;
            }

            // 调用方法处理数据
            const variants = processDataAndFillKeys();

            // 调用处理方法
            const skuList = handleSingleAttributeVariants(variants, publicAttributeKeys);

            var box =
            {
                "Title": title,
                "DetailedDescription": detailedDesc,
                "BriefDescription": briefDesc,
                "ImageUrl": productImgs.join("|"),
                "PropertyName": JSON.stringify(publicAttributeKeys),
                "PlatformCategoryId": "",
                "SourceUrl": window.location.href,
                "VideoUrl": "",
                "IsClaimed": false,
                "SourcePlatform": 7,
                "Tags": [],
                "Remark": "",
                "CreateTime": "1900-01-01 00:00:00",
                "Parameters": params,
                "PlatformCategoryName": ""
            };

            const variantArr = skuList.map(item => {
                return {
                    ...item, //复制原对象的所有属性
                    Property: JSON.stringify(item.Property), //覆盖Property属性
                    Price: price //添加 price 属性
                };
            });

            //没有变体新增一条单变体
            if (variantArr.length == 0) {
                variantArr.push({
                    Price: price,
                    VariantImageUrl: productImgs.length > 0 ? productImgs[0] : ""
                });
            }

            const pageData = {
                box,
                variantArr
            }

            console.log('pageData', JSON.stringify(pageData));
            sendResponse({ "isLinkCollect": true, pageData });

            // 以下代码为2026-04-20前可以调用接口时的版本
            // let data = {};
            // data.info = window._LiSellingJoomSign_
            // sendResponse(data);
            return true;
        } else if (request.Type === 'GetTaoBaoText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetPinDuoDuoText') {
            var jsonStr = "none";
            //判断当前页面域名是否为"https://pifa.pinduoduo.com/*",
            if (document.URL.indexOf('pifa.pinduoduo.com') >= 0) {
                var jsondata = "none";
                let url = document.URL;
                let data = {};
                data.url = document.URL;
                let param = url;
                if (url.indexOf("&") > -1) {
                    param = param.substring(url.indexOf("=") + 1, url.indexOf("&"));
                } else {
                    param = param.substring(url.indexOf("=") + 1);
                }
                let antiContent = "0arAfxndGylBYgEhgv4SUxfUg2Dfdk48vhhLuJuEP6bHozEP9v5TjXOhIzNrhFjcpOH5HSF2TzQTPOgqwQTU4tZ4x7Z4eP8x9dFwDISiRTvSbMwW9l9eEshpRAp8rg5HGoa3tzK_eEon1S5UsswmtLqwzYNosjOCoT6XVd1atOuse_tyt7gmqal6lN5gKzJob-6t4diu8aUPbNbs27wQLwEu-pmX1PIzLM0c3fsclrqMal7XihpyNIDjh50xywy5FtDbdkgcPaxv1_GaGvfUAv9Whx0rvIqNzpFw-T1loX7c1EhvwCtqf9n4JYrcwJFmQrTgVhexq96cGXXGLCq0rhBVGPVp8uvZVFygAzoHsHNIlYOos0yfkqPuFRQoJyAI9m_gRGLF7qCsNgwHWS5BwAke14DNFEzjh7px9TLqEjzjOJmWALdxYXA4q8X1c8SDGyxNuRX-b-RNTux1gj4wtZxriZNRuhKAGyANaO69mL3wigSIwqqBZy8_3zL1TuoQWQqaixqNTfAfxei9TqOUkMlyPqkR";
                if (window._LiSellingPinDuoDuoSign_ != null) {
                    antiContent = window._LiSellingPinDuoDuoSign_['Anti-Content'];
                }
                var propertyInfo = "";
                var Detail = "";
                $.ajax({
                    type: "POST",
                    headers: {
                        "anti-content": antiContent
                    },
                    withCredentials: true,
                    url: "https://pifa.pinduoduo.com/pifa/goods/queryGoodsPropertyInfo",
                    data: JSON.stringify({ "goodsId": param }),
                    async: false,
                    contentType: "application/json",
                    dataType: "json",
                    success: function (results) {
                        propertyInfo = JSON.stringify(results);
                    },
                    error: function (results) {
                    }
                });
                $.ajax({
                    type: "POST",
                    headers: {
                        "anti-content": antiContent
                    },
                    withCredentials: true,
                    url: "https://pifa.pinduoduo.com/pifa/goods/queryGoodsDetail",
                    data: JSON.stringify({ "goodsId": param }),
                    async: false,
                    contentType: "application/json",
                    dataType: "json",
                    success: function (results) {
                        Detail = JSON.stringify(results);

                    },
                    error: function (results) {
                    }
                });
                data.html = Detail;
                data.propertyInfo = propertyInfo;
                sendResponse(data);
                // sendResponse({ "isLinkCollect": true });
                return true;
            }

            //获取页面的价格数据
            let priceText = "";
            const container = document.querySelector("div.goods-container-v2");
            if (container) {
                // 查找 container 内的 span.kxqW0mMz
                const span = container.querySelector("span.kxqW0mMz");
                if (span) {
                    priceText = span.textContent.trim();
                }
            }
            if (priceText == "") {
                try {
                    priceText = document.querySelector('span.yahImUGW').innerText;//页面价格
                } catch (e) { }
            }

            var scripts = document.querySelectorAll("body > script");
            for (var i = 0; i < scripts.length; i++) {
                if (scripts[i].innerHTML.indexOf('window.rawData=') != -1)
                    jsonStr = scripts[i].innerHTML.replace("window.rawData=", "var jsonData=");
                if (jsonStr != "none")
                    i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
            }
            if (jsonStr != "none") {
                jsonData = undefined;
                let interpreter = new eval5.Interpreter(window);
                let result = interpreter.evaluate(jsonStr);
                if (jsonData && typeof (jsonData) != 'undefined') {
                    sendResponse({ jsonData, priceText });
                } else {
                    sendResponse({ jsonData: "none", priceText });
                }
            } else {
                sendResponse({ jsonData: "none", priceText });
            }

            return true;
        } else if (request.Type === 'GetOzonText') {
            var jsonStr = "none";
            varnameArr = [];
            var scripts = document.querySelectorAll("body > script");

            for (var i = 0; i < scripts.length; i++) {
                if (scripts[i].innerHTML.indexOf('window.__NUXT__') != -1) {
                    jsonStr = scripts[i].innerHTML.split("window.__NUXT__")[1];
                }
                if (jsonStr != "none")
                    i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
            }
            var breadCrumbs = $(".e4h").children();
            var categoryName = '';
            if (breadCrumbs.length > 0) {
                categoryName = breadCrumbs[breadCrumbs.length - 1].innerText
            }
            url = window.location.pathname;
            var data;
            // 兼容两种页面json读取方式
            if (jsonStr.indexOf('={}') == 0 || jsonStr == "none") {
                for (var i = 0; i < scripts.length; i++) {
                    if (scripts[i].innerHTML.indexOf('window.__NUXT__.state') != -1) {
                        jsonStr = scripts[i].innerHTML.replace("window.__NUXT__.state", "var jsonData");
                    }
                    if (jsonStr != "none")
                        i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
                }
                varnameArr.push("jsonData");
            } else {
                jsonStr = 'jsondata' + jsonStr;
                varnameArr.push("jsondata");
            }

            if (jsonStr != "none") {
                jsonData = undefined;
                let interpreter = new eval5.Interpreter(window);
                let result = interpreter.evaluate(jsonStr);
                if (jsonData) {
                    data = JSON.parse(jsonData).seo;
                }
                if (jsondata) {
                    data = jsondata.state.seo;
                }

                // 主数据
                var obj = undefined;
                try {
                    obj = JSON.parse(data.script[0].innerHTML)
                } catch (e) { }

                if (data.link && data.meta && data.title && !data.script) {
                    sendResponse({
                        Info: "刷新重试",
                    });
                    return;
                }

                //获取变体参数
                var aspectsModel = null;
                var PropertyName = [];
                var parameters = [];
                var skuLinks = [];
                var skus = [];
                var imageUrls = [];
                var aspectsJson = $("div[id^='state-webAspects-']").attr("data-state");
                var webGalleryJson = $("div[id^='state-webGallery-']").attr("data-state");

                var videoUrl = "";
                if (aspectsJson) {//多变体
                    aspectsModel = JSON.parse(aspectsJson);
                    var webGalleryModel = JSON.parse(webGalleryJson);

                    //变体参数名
                    //PropertyName = aspectsModel.aspects.map(x => x.descriptionRs[0].content.replace(": ", "").replace(":", ""));

                    //当前页面sku、sku链接
                    var selfSku = {};
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

                            if (!skuLinks.some(y => y.SkuCode == variant.sku)) {
                                skuLinks.push({
                                    SkuCode: variant.sku,
                                    Link: variant.link,
                                    ImageUrls: null,
                                });
                            }
                        });
                    });
                    selfSku.VariantImageUrl = webGalleryModel.images.map(x => x.src);
                    skus.push(selfSku);
                    skuLinks.forEach(x => {
                        if (x.SkuCode == webGalleryModel.sku) {
                            x.ImageUrls = selfSku.VariantImageUrl;
                        }
                    });

                    //获取视频链接
                    if (webGalleryModel.videos && webGalleryModel.videos.length > 0) {
                        videoUrl = webGalleryModel.videos[0].url;
                    }

                    //获取视频链接
                    if (webGalleryModel.videoCover && webGalleryModel.videoCover.url) {
                        videoUrl = webGalleryModel.videoCover.url;
                    }
                } else if (webGalleryJson) {//单变体
                    var webGalleryModel = JSON.parse(webGalleryJson);

                    //获取视频链接
                    if (webGalleryModel.videoCover && webGalleryModel.videoCover.url) {
                        videoUrl = webGalleryModel.videoCover.url;
                    }

                    //获取视频链接
                    if (webGalleryModel.videos && webGalleryModel.videos.length > 0) {
                        videoUrl = webGalleryModel.videos[0].url;
                    }

                    skus.push({
                        Price: 0,
                        SkuCode: webGalleryModel.sku,
                        Property: "[]",
                        Currency: "RUB",
                        VariantImageUrl: webGalleryModel.images.map(x => x.src),
                    });
                }

                //获取主题标签数据
                try {
                    const container = document.querySelector('div[data-widget="webHashtags"]');
                    let hashtagTexts = Array.from(container.querySelectorAll('div[title]')).map(item => item.getAttribute('title'));
                    if (hashtagTexts.length > 0) {
                        parameters.push({
                            "Key": "#Хештеги",
                            "Value": hashtagTexts.join(" ")
                        });
                    }
                } catch { }

                if (obj != undefined) {
                    sendResponse({
                        Info: obj,
                        //PropertyName: PropertyName,
                        Parameters: parameters,
                        SkuLinks: skuLinks,
                        Skus: skus,
                        Url: url,
                        VideoUrl: videoUrl,
                        CategoryName: categoryName
                    });
                }
                else {
                    sendResponse("none");
                }

            } else {
                sendResponse("none");
            }
            return true;
        } else if (request.Type === 'GetLazadaText') {
            sendResponse({ "isLinkCollect": true });
            return true;
            // var jsonStr = "none";
            // var scripts = document.querySelectorAll("body > script");

            // for (var i = 0; i < scripts.length; i++) {
            //     if (scripts[i].innerHTML.indexOf('__moduleData__') != -1) {
            //         jsonStr = scripts[i].innerHTML.split("__moduleData__ =")[1].split("};")[0];
            //     }

            //     if (jsonStr != "none")
            //         i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
            // }
            // var jsondata = JSON.parse(jsonStr + "}");

            // if (jsondata != undefined && jsondata.data != undefined && jsondata.data.root != undefined && jsondata.data.root.fields != undefined) {
            //     {
            //         if (document.querySelector(".pdp-mod-section-title") != null)
            //             jsondata.data.root.fields.ExtDescText = document.querySelector(".pdp-mod-section-title").innerText;
            //         else
            //             jsondata.data.root.fields.ExtDescText = "";

            //         sendResponse(jsondata.data.root.fields);
            //     }
            // } else {
            //     sendResponse("none");
            // }

            // return true;
        } else if (request.Type === 'GetEbayText') {
            var data = getEbayPageData(document);
            if (data) {
                sendResponse(data);
            } else {
                sendResponse("none");
            }
            return true;
        } else if (request.Type === 'GetEbayHtmlData') {
            var parser = new DOMParser();
            var doc = parser.parseFromString(request.html, "text/html");
            var ebayData = getEbayPageData(doc);

            sendResponse(ebayData || "none");
            return true;
        } else if (request.Type === 'GetCouPangText') {
            var tabUrl = window.location.href
            $.ajax({
                url: tabUrl,
                type: "POST",
                timeout: 300000,
                async: false,
                success: function (response) {
                    // 检查响应中是否不包含特定模式
                    if (!response.match(/exports\.sdp\s=\s(.*);\\s+exports\.sdpIssueTypes/)) {
                        try {
                            // 提取所有<script>标签内容
                            var scriptRegex = /<script>([\s\S]*?)<\/script>/g;
                            var scriptContents = [];
                            var matchedScript;
                            var couponScript = "";

                            // 收集所有脚本内容
                            while ((matchedScript = scriptRegex.exec(response))) {
                                scriptContents.push(matchedScript[1].trim());
                            }

                            // 查找包含特定内容的脚本
                            for (var i = 0; i < scriptContents.length; i++) {
                                if (scriptContents[i].indexOf("applyNewPostCouponModule") !== -1) {
                                    couponScript = scriptContents[i];
                                    break; // 找到后就可以退出循环
                                }
                            }

                            // 如果找到目标脚本，解析其中的属性信息
                            if (couponScript) {
                                try {
                                    // 解析JSON数据
                                    var parsedScript = JSON.parse(couponScript.substring(19, couponScript.length - 1));
                                    var scriptContent = parsedScript[1].substring(3, parsedScript[1].length);
                                    var parsedContent = JSON.parse(scriptContent);
                                    //console.log("parsedContent", JSON.stringify(parsedContent));
                                    var atfData = findAtfData(parsedContent);
                                    sendResponse(atfData);
                                    // 提取属性信息
                                    // var atfData = parsedContent[2][3].children[1][3]?.atfData || {};
                                    // result.propertyInfo = JSON.stringify(atfData);
                                } catch (parseError) {
                                    // 解析错误静默处理
                                }
                            }
                        } catch (error) {
                            // 错误静默处理
                        }
                    }

                },
                error: function () {
                }
            });
            return true;

            //以下是旧方法获取页面json数据
            // var jsonStr = "none";
            // var scripts = document.querySelectorAll("head > script");

            // for (var i = 0; i < scripts.length; i++) {
            //     if (scripts[i].innerHTML.indexOf('exports.sdp') >= 0 && scripts[i].innerHTML.indexOf('exports.sdp') < 50)
            //         jsonStr = scripts[i].innerHTML.split("exports.sdp")[1].split("exports.sdpIssueTypes")[0];
            //     if (jsonStr != "none")
            //         i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
            // }
            // jsondata = undefined;
            // let interpreter = new eval5.Interpreter(window);
            // let result = interpreter.evaluate('jsondata ' + jsonStr);
            // if (result) {
            //     sendResponse(result);
            // } else {
            //     sendResponse("none");
            // }
            // return true;
        } else if (request.Type === 'GetShopeeText') {
            var shopeeApiUrlObj = getShopeeHtmlUrl(request.sourceUrl)
            if (window._LiSellingShopeeSign_ != undefined) {
                var jsondata = "none";
                var headObj = window._LiSellingShopeeSign_;
                var shopeeV4Url = headObj.shopeeV4Url ? headObj.shopeeV4Url : shopeeApiUrlObj.v4Url;
                var shopeeHeadersObj = {
                    'anti-content': '0aoAfaNddyhYY9T8kxVCQC0_P2EfPw_tuZL8SiH1_tdWSZQK47TOPFLHwaLLv5eaBh6SdUl8G5o1yUtsxbPSqu3Xiinw5lOsC9o99LmfaecBR9PG1hzeoAP5c7f8UP39qRVPhHaDa1qWcObKHVZya_IusQkmfnx3AvF-k3Nv0vaSDy8Ae6jZgr0wICTCuNNhvLy22nmcK__T6_stNaRiI7tv2jelsAwOubfPrt0Cs0f2BXi5VVQHgraqT2J0Q7m9EbYo9g9GjBVMCuX2K5pII9VmQWnMedw56YedQ99q-mlA959tL5dZ6BHWGrIA4oFqy_mKPqJHRC8pijT0nx6vuGkjD_QDp19joS428x05kIQx8jVuAaas3Qja23Chsj5ZqgZjXv6x2EglYfDoTbw8aZOf-Sjt2IQGce_Cu100iQqETWKE16TAbdHxUnYX1RGKWtU6ACxP1UItD1XHLCcRIK92iLzLkFfea1WFvXqj-Sq11e2aGiBvloc1tF4WqT-KR7KjwuKyeh-5NIUFmDbuHI6y7Tm7vRLgajA0fWVKLdRhngrj8J7J9zHH3WRA_1J2rYBCBmo85xK53icGUMomuXMt8UmvcB9LWObIRmGovBEho'
                };

                delete headObj['shopeeV4Url'];//删除URL路径

                shopeeHeadersObj = $.extend(shopeeHeadersObj, headObj);
                $.ajax({ //调用Shopee的获取数据的接口
                    type: "GET",
                    headers: shopeeHeadersObj,
                    withCredentials: true,
                    url: shopeeV4Url,
                    async: false,
                    contentType: "application/json",
                    dataType: "json",
                    success: function (results) {
                        results.version = "4";
                        //把得到的数据放到html字段里面
                        jsondata = JSON.stringify(results);
                        ;
                    },
                    error: function (results) {
                    }
                });

                sendResponse(jsondata);
            } else {
                sendResponse({ isBathCollect: true });
            }
            return true;
        } else if (request.Type === 'GetTmallText') {
            var id = '';
            if ($('#aliww-click-trigger') && $('#aliww-click-trigger').length > 0)
                id = $('#aliww-click-trigger').attr('data-item');

            sendResponse({ "isLinkCollect": true, "id": id });
            return true;
        } else if (request.Type === 'GetJDText') {
            var tabUrl = window.location.href;
            //标题
            let title = document.querySelector('.sku-title .sku-title-name').innerText;

            //价格
            let price = 0;
            const priceDoc = document.querySelector('.product-price--main .product-price--value');
            if (priceDoc)
                price = parseFloat(priceDoc.innerText);

            //视频链接
            let videoUrl = "";
            const videoDoc = document.querySelector('video.player-video-element');
            if (videoDoc)
                videoUrl = videoDoc.src;

            //产品图片
            let productImgs = Array.from(document.querySelectorAll('.image-carousel-track .image')).map(img => img.src);

            //变体
            const groups = document.querySelectorAll('.specifications-panel-content .specification-group');
            const properties = [];

            groups.forEach(group => {
                const key = group.querySelector('.specification-group-label').innerText.trim();
                const items = group.querySelectorAll('.specification-item-sku');
                const values = [];
                items.forEach(item => {
                    const value = item.querySelector('.specification-item-sku-text').innerText.trim();
                    // 只有包含图片的规格（如颜色）才提取图片，其他（如版本）图片为 null
                    const img = item.querySelector('img') ? item.querySelector('img').src : null;
                    values.push({ value, img });
                });
                properties.push({ key, values });
            });

            //生成笛卡尔积SKU
            function generateSKUs(props) {
                return props.reduce((acc, currProp) => {
                    // 第一次循环时，acc 是空的，直接生成基础对象
                    if (acc.length === 0) {
                        return currProp.values.map(val => ({
                            VariantImageUrl: val.img.replace(/s48x48_jfs/g, "s1440x1440_jfs"),
                            Property: [{ Key: currProp.key, Value: val.value }],
                        }));
                    }

                    // 后续循环，将现有结果与新属性进行组合
                    const result = [];
                    acc.forEach(accItem => {
                        currProp.values.forEach(val => {
                            result.push({
                                // 如果当前项有图片，优先使用当前项的图片；否则保留原图片（通常颜色图最重要）
                                VariantImageUrl: val.img || accItem.VariantImageUrl,
                                Property: [...accItem.Property, { Key: currProp.key, Value: val.value }]
                            });
                        });
                    });
                    return result;
                }, []);
            }
            const skuList = generateSKUs(properties);

            //富文本描述1  滚动页面抓取图片  ==>滚动采集页面需解开此方法
            async function scrollAndWait() {
                return new Promise((resolve, reject) => {
                    let targetPosition = window.scrollY + 4000;
                    const timeoutDuration = 8000;
                    let timeoutReached = false;

                    function scrollStep() {
                        if (window.scrollY < targetPosition) {
                            window.scrollBy(0, 50);
                            requestAnimationFrame(scrollStep);
                        } else {
                            var box =
                            {
                                "Title": title,
                                "DetailedDescription": getDetailedDesc(),
                                "BriefDescription": getBriefDesc(),
                                "ImageUrl": productImgs.join("|"),
                                "PropertyName": properties.length > 0 ? JSON.stringify(properties.map(item => item.key)) : "[]",
                                "PlatformCategoryId": "",
                                "SourceUrl": tabUrl,
                                "VideoUrl": videoUrl,
                                "IsClaimed": false,
                                "SourcePlatform": 18,
                                "Tags": [],
                                "Remark": "",
                                "CreateTime": "1900-01-01 00:00:00",
                                "Parameters": [],
                                "PlatformCategoryName": ""
                            };

                            //页面拿不到接口拿
                            if (!box.DetailedDescription)
                                box.DetailedDescription = getDetailedDesc2()

                            const variantArr = skuList.map(item => {
                                return {
                                    ...item, //复制原对象的所有属性
                                    Property: JSON.stringify(item.Property), //覆盖Property属性
                                    Price: price //添加 price 属性
                                };
                            });

                            //没有变体新增一条单变体
                            if (variantArr.length == 0) {
                                variantArr.push({
                                    Price: price
                                });
                            }

                            const pageData = {
                                box,
                                variantArr
                            }

                            console.log('pageData', JSON.stringify(pageData));
                            sendResponse({ "isLinkCollect": true, pageData });
                        }
                    }

                    scrollStep();
                });
            }

            //抓取DOM获取文本描述
            function getBriefDesc() {
                //文本描述
                var briefDescription = "";
                try {

                    let resultString = "";

                    // 获取所有 goods-base 下的 item div
                    const itemDivs = document.querySelectorAll('div._scoped_wkh1b_1 div.item');

                    // 将 NodeList 转换为数组以便使用数组方法（如 forEach）
                    const itemsArray = Array.from(itemDivs);

                    itemsArray.forEach(div => {
                        const labelEl = div.querySelector('div.label');
                        const valueEl = div.querySelector('div.value');

                        const label = labelEl ? labelEl.textContent.trim() : '';
                        const value = valueEl ? valueEl.textContent.trim() : '';

                        if (label && value) {
                            // 组合成 "flexCenterText : adaptiveText" 并换行
                            resultString += `${label} : ${value}\n`;
                        }
                    });

                    briefDescription = resultString;
                } catch (e) { }

                return briefDescription;
            }

            //抓取DOM获取富文本描述
            function getDetailedDesc() {
                let detailedDescriptionArr = [];
                // 能够匹配 url("...") 或 url('...') 或 url(...) 的格式
                const srcChecker = /url\(\s*?['"]?\s*?(\S+?)\s*?["']?\s*?\)/i;

                // 2. 获取父级容器 .ssd-module-wrap
                const wrapElement = document.querySelector('.ssd-module-wrap');

                if (wrapElement) {
                    // 3. 在父级容器内查找所有 .ssd-module 元素
                    const modules = wrapElement.querySelectorAll('.ssd-module');
                    //const bgImages = [];

                    modules.forEach((module, index) => {
                        // 4. 获取计算后的样式 (Computed Style)
                        // 必须使用 getComputedStyle 才能获取到 CSS 文件中定义的背景图
                        const style = window.getComputedStyle(module, null);
                        const bgImageProp = style.getPropertyValue('background-image');

                        // 5. 使用正则提取 URL
                        const match = srcChecker.exec(bgImageProp);

                        if (match && match[1]) {
                            const imgUrl = match[1];
                            detailedDescriptionArr.push(`<div><img src='${imgUrl}'></div>`);
                        }
                    });

                } else {
                    console.error('未找到 .ssd-module-wrap 元素');
                }

                return detailedDescriptionArr.join('');
            }

            //富文本描述2  接口获取图片
            function getDetailedDesc2() {
                let detailedDescriptionArr = [];
                const match = tabUrl.match(/item\.jd\.com\/(\d+)\.html/);
                const skuId = match ? match[1] : null;
                const data = {
                    skuId
                };

                // JSON.stringify 默认会添加换行和缩进,如下这样不会
                const jsonString = JSON.stringify(data, null, 2);

                //使用 encodeURIComponent 对整个字符串进行编码
                const encodedData = encodeURIComponent(jsonString);

                let descUrl = `https://api.m.jd.com/?functionId=pc_item_getWareGraphic&body=${encodedData}&appid=item-v3`;
                $.ajax({
                    url: descUrl,
                    method: 'GET',
                    dataType: 'text',
                    async: false,
                    success: function (data) {
                        try {
                            const descData = JSON.parse(data);
                            let descHtml = descData?.data?.graphicContent;

                            descHtml = descHtml
                                .replace(/&lt;/g, "<")
                                .replace(/&gt;/g, ">")
                                .replace(/&quot;/g, '"');

                            const container = document.createElement("div");
                            container.innerHTML = descHtml;

                            const imgDocs = container.querySelectorAll("img");

                            let imgUrls = [];

                            imgDocs.forEach(img => {
                                let url = img.getAttribute("data-lazyload") || img.getAttribute("src");

                                if (!url) return;

                                if (!url.startsWith("http")) {
                                    url = "https:" + url;
                                }

                                imgUrls.push(url);
                            });

                            //情况2
                            if (imgUrls.length == 0) {
                                const bgMatches = descHtml.match(/background-image\s*:\s*url\(([^)]+)\)/gi);
                                if (bgMatches) {
                                    bgMatches.forEach(item => {
                                        let match = item.match(/url\(([^)]+)\)/i);
                                        if (match && match[1]) {
                                            let url = match[1].replace(/["']/g, "");

                                            if (!url.startsWith("http")) {
                                                url = "https:" + url;
                                            }

                                            imgUrls.push(url);
                                        }
                                    });
                                }
                            }

                            imgUrls = imgUrls.filter((item, index) => {
                                return imgUrls.indexOf(item) === index;
                            });

                            imgUrls.forEach(url => {
                                detailedDescriptionArr.push(`<div><img src='${url}'></div>`);
                            });

                        } catch (e) { }
                    },
                    error: function (jqXHR, textStatus, errorThrown) {
                    }
                });
                return detailedDescriptionArr.join('');
            }

            // 使用 async/await 确保顺序执行 ==>滚动采集页面需解开此方法
            (async () => {
                try {
                    if (!tabUrl || tabUrl == "https://www.jd.com/" || tabUrl == "https://www.jd.com" || tabUrl.indexOf("list.jd.com") > -1) {
                        throw new Error("产品列表页不滑动页面采集图片");
                    }
                    await scrollAndWait(); // 等待滚动和 DOM 加载完成
                } catch (error) {
                    getDescData2(); // 然后执行
                }
            })();

            return true;

        } else if (request.Type === 'GetCdiscountText') {
            var jsonStr = "none";
            if (document.getElementById("fpZnPrdMain")) {
                //Cdiscount旧版
                var title = document.getElementsByClassName("fpDesCol")[0].getElementsByTagName("h1")[0].innerText;
                // var title = $('*[itemprop="name"]').text;//标题
                var price = document.querySelector("span[itemprop='price']").getAttribute("content");
                // var price = $('*[itemprop="price"]').getAttribute('content'); //价格
                var vantList = [];
                var mainImg = [];
                var descStr = [];
                var vantStyleFlag = 1;
                var vantTitles = document.getElementsByClassName("fpVariationGroupTitleContainer");
                var vantVals = document.getElementsByClassName("fpVariationGroupOptionsContainer");
                var descHtml = document.getElementsByClassName("testSep")[2].innerHTML;
                var desclable = document.getElementsByClassName("testSep")[2].getElementsByTagName("tr");
                var mainImgLi = document.getElementsByClassName("jsFpZoomPic")[0].getElementsByTagName("li");

                if (vantTitles == null || vantTitles.length == 0) {
                    vantStyleFlag = 2;
                    //服装单变体
                    vantTitles = document.getElementsByClassName("fpSizeSelector");
                    vantVals = document.getElementsByClassName("jsSltSize");
                }
                //[0].getElementsByTagName("img")[0].getAttribute("src");

                //[0].getElementsByClassName("fpVariationGroupTitle")[0].innerText
                var scripts = document.querySelectorAll("head > script");

                // for (var i = 0; i < scripts.length; i++) {
                //     if (scripts[i].innerHTML.indexOf('\"@type\":\"Product\"') >= 0)
                //         jsonStr = scripts[i].innerHTML;
                //     if (jsonStr != "none")
                //         i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
                // }

                //获取主图
                for (var i = 0; i < mainImgLi.length; i++) {
                    if (mainImgLi[i].getElementsByTagName("img").length > 0) {
                        var imgStr = mainImgLi[i].getElementsByTagName("img")[0].getAttribute("src");
                        var imgStrList = imgStr.split("/");
                        var sizeStr = imgStrList.find(x => x.indexOf("x") > -1 && x.length == 7);
                        if (sizeStr != null) {
                            imgStr = imgStr.replace(sizeStr, "700x700");
                        }
                        mainImg.push(imgStr);
                    }
                }

                //多变体，电子产品变体
                //获取变体title
                for (var i = 0; i < vantTitles.length; i++) {
                    var vanrs = [];
                    var vantName = (vantStyleFlag == 1 ? vantTitles[i].getElementsByClassName("fpVariationGroupTitle")[0].innerText : vantTitles[i].innerText).split(':')[0].trim();

                    //变体内容
                    if (vantVals.length > i) {
                        var vantval = vantStyleFlag == 1 ? vantVals[i].getElementsByTagName("div") : vantVals[i].getElementsByTagName("option");
                        var vantImg = vantVals[i].getElementsByTagName("img"); //变体图片

                        //变体详细子集
                        for (var j = 0; j < vantval.length; j++) {
                            var proval = vantStyleFlag == 1 ? vantval[j].getAttribute("data-message") : vantval[j].innerText;
                            var img = "";
                            if (vantImg && vantImg.length > j) {
                                img = vantImg[j].getAttribute("src");
                                var imgStrList = img.split("/");
                                var sizeStr = imgStrList.find(x => x.indexOf("x") > -1 && x.length == 7);
                                if (sizeStr != null) {
                                    img = img.replace(sizeStr, "700x700");
                                }
                            }
                            if (proval && proval != null && proval != '' && proval != 'Choisissez votre taille')
                                vanrs.push({ "option": proval, "imageUrl": img });
                        }

                        if (vanrs.length > 0)
                            vantList.push({ key: vantName, value: vanrs });
                    }
                }

                //获取参数
                if (desclable != null) {
                    //获取参数
                    for (let i = 0; i < desclable.length; i++) {
                        if (desclable[i].getElementsByTagName("td") != null && desclable[i].getElementsByTagName("td").length > 0) {
                            var paramVal = desclable[i].getElementsByTagName("td")[0].innerText;
                            paramVal = paramVal.replace(/[\\n]/g, "").replace('"', '');
                            var strObj = { Key: desclable[i].getElementsByTagName("th")[0].innerText, Value: paramVal };
                            descStr.push(strObj);
                        }
                    }
                }
                var breads = $(".o-breadcrumb").children("li");
                var categoryName = '';
                if (breads != null && breads.length > 0) {
                    var categroy = breads[breads.length - 2];
                    categoryName = categroy.innerText.trim();
                }
                sendResponse({
                    "title": title,
                    "price": price,
                    "mainImg": mainImg,
                    "vantList": vantList,
                    "descHtml": descHtml,
                    "descStr": descStr,
                    "categoryName": categoryName
                });
            } else {
                //Cdiscount新版
                //标题
                var title = document.querySelector('h1[data-e2e="title"]').innerText;

                //价格 
                //var price = document.querySelector('#product-scene span.gIpMGn').innerText;
                var price = document.querySelector('[data-e2e="price"]').innerText;

                //图片
                var mainImg = [];
                var imgDivs = document.querySelectorAll('div[data-e2e="image"] section div');

                for (var i = 0; i < imgDivs.length; i++) {
                    if (imgDivs[i].getElementsByTagName("img").length > 0) {
                        var imgStr = imgDivs[i].getElementsByTagName("img")[0].getAttribute("src");
                        var imgStrList = imgStr.split("/");
                        var sizeStr = imgStrList.find(x => x.indexOf("x") > -1 && x.length == 7);
                        if (sizeStr != null) {
                            imgStr = imgStr.replace(sizeStr, "700x700");
                        }
                        mainImg.push(imgStr);
                    }
                }

                //属性
                var descStr = [];
                var desclable = document.querySelectorAll('table.sc-bvFjSx.gDUrnw tbody tr');
                if (desclable.length > 0) {
                    //获取参数
                    for (let i = 0; i < desclable.length; i++) {
                        if (desclable[i].getElementsByTagName("td") != null && desclable[i].getElementsByTagName("td").length > 0) {
                            var paramVal = desclable[i].getElementsByTagName("td")[0].innerText;
                            paramVal = paramVal.replace(/[\\n]/g, "").replace('"', '');
                            var strObj = { Key: desclable[i].getElementsByTagName("th")[0].innerText, Value: paramVal };
                            descStr.push(strObj);
                        }
                    }
                }

                //分类
                var categoryLis = document.querySelectorAll('ul.sc-cCcXHH.enFuyN li');
                var categoryName = '';
                if (categoryLis != null && categoryLis.length > 0) {
                    var categroy = categoryLis[categoryLis.length - 2];
                    categoryName = categroy.innerText.replace(/\//g, '').trim();
                }

                //描述
                var descHtml = "";
                var baseDescDoc = document.querySelector('div.cgfqOY');
                if (baseDescDoc)
                    descHtml += baseDescDoc.innerHTML;

                var descDom1 = document.querySelector('iframe[title="Descriptif Marketing"]');
                if (descDom1) {
                    var iframeHtml = descDom1.getAttribute('srcdoc');
                    descHtml += `<p>${iframeHtml}</p>`;
                }

                var descDom2 = document.querySelector('p.sc-1ps9gfi-1')
                if (descHtml == "" && descDom2) {
                    descHtml = `<p>${descDom2.innerHTML}</p>`;
                }

                var descDom3 = document.querySelector('div.hiTDhu')
                if (descHtml == "" && descDom3) {
                    descHtml = `<p>${descDom3.innerHTML}</p>`;
                }

                if (descHtml == "") {
                    try {
                        let inputDom = document.querySelector('#collapse-MarketingDescription');
                        let parentDom = inputDom.parentNode;
                        let descDom4 = parentDom.querySelector('div.PanelContent');
                        descHtml = `<p>${descDom4.innerText}</p>`;
                    } catch (e) { }
                }
                //变体
                var vantList = [];
                var vantDivs = document.querySelectorAll('div[data-e2e="variant-block"]');
                if (vantDivs && vantDivs.length > 0) {
                    for (var i = 0; i < vantDivs.length; i++) {
                        var vantName = vantDivs[i].querySelector("p strong").textContent.replace(":", "").trim();
                        var vants = [];
                        var vantLis = vantDivs[i].querySelectorAll("li");
                        if (vantLis && vantLis.length > 0) {
                            for (var j = 0; j < vantLis.length; j++) {
                                var option = vantLis[j].getAttribute("title");
                                var imageUrl = "";
                                if (vantLis[j].querySelector("img")) {
                                    var imageUrl = vantLis[j].querySelector("img").getAttribute("src").trim();
                                    var imgStrList = imageUrl.split("/");
                                    var sizeStr = imgStrList.find(x => x.indexOf("x") > -1 && x.length == 7);
                                    if (sizeStr != null) {
                                        imageUrl = imageUrl.replace(sizeStr, "700x700");
                                    }
                                }
                                vants.push({ "option": option, "imageUrl": imageUrl });
                            }
                        }
                        if (vants.length > 0)
                            vantList.push({ key: vantName, value: vants });
                    }
                }
                sendResponse({
                    "title": title,
                    "price": price,
                    "mainImg": mainImg,
                    "vantList": vantList,
                    "descHtml": descHtml,
                    "descStr": descStr,
                    "categoryName": categoryName
                });
            }
            return true;
        } else if (request.Type === 'GetMercadoliText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetYiwugoText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetVVicText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetSooxieText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetDunhuangText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetTuGouText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetWSYText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetETSYText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetOnBuyText') {
            sendResponse({ "isLinkCollect": true, "currency": "GBP" });
            return true;
        } else if (request.Type === 'GetTiktokText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetWildberriesText') {
            let videoUrl = "";
            try {
                videoUrl = document.querySelector('video.j-video-thumb-preview').getAttribute('src');
            } catch (e) { }
            sendResponse({ "isLinkCollect": true, "videoUrl": videoUrl });
            return true;
        } else if (request.Type === 'GetFruugoText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetSheinText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetYandexText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetSaleyeeText') {
            sendResponse({ "isLinkCollect": true });
            return true;
        } else if (request.Type === 'GetArkSwiftText') {
            var sourceUrl = request.sourceUrl || window.location.href;
            var itemCode = "";
            var url = sourceUrl.split("?")[0];
            if (url.indexOf("~") > -1) {
                itemCode = url.substring(url.lastIndexOf("~") + 1);
            }
            if (!itemCode) {
                sendResponse("none");
                return true;
            }
            var requestUrl = "https://www.arkswift.com/api/v1/rest/product-details?id=" + encodeURIComponent(itemCode);
            fetch(requestUrl)
                .then(response => response.json())
                .then(response => {
                    if (response && response.code == 200 && response.data) {
                        sendResponse({ "isLinkCollect": true, "Data": response.data });
                    } else {
                        sendResponse("none");
                    }
                })
                .catch(() => {
                    sendResponse("none");
                });
            return true;
        } else if (request.Type === 'Alter') {
            if (request.Message === '添加失败，采集箱数量保存上限100万行，请删除已认领或过期数据。') {
                CloseCategoryCollectProgressModal();
                ShowBottomMenu();
            }
            if (request.Url && request.Url != null && request.Url != '') {
                GrowlNotification.notify({
                    title: '无忧易售',
                    description: request.Message,
                    type: request.MessageType,
                    position: 'top-right',
                    closeTimeout: 7000,
                    closeWith: "button",
                    image: { visible: true, customImage: config.logoBase64 },
                    showButtons: true,
                    buttons: {
                        action: {
                            text: request.ActionBtnText && request.ActionBtnText != null && request.ActionBtnText != '' ? request.ActionBtnText : '是',
                            callback: function () {
                                window.open(request.Url, "_blank");
                            }
                        },
                        cancel: {
                            text: '取消',
                            callback: function () {
                            }
                        }
                    }
                });
            } else {
                GrowlNotification.notify({
                    title: '无忧易售',
                    description: request.Message,
                    type: request.MessageType,
                    position: 'top-right',
                    closeTimeout: 3000,
                    image: { visible: true, customImage: config.logoBase64 },
                });
            }
            sendResponse('');
            return true;
        } else if (request.Type === 'NotificationShow') {
            if (!request.Key || NotificationList.find(x => x.Key == request.Key)) {
                sendResponse('');
                return true;
            }

            options = {
                title: '无忧易售',
                description: request.Message,
                type: request.MessageType,
                position: 'top-right',
                closeTimeout: 0,
                image: { visible: true, customImage: config.logoBase64 },
            }

            gn = new GrowlNotification(options)
            gn.show();
            NotificationList.push({ Key: request.Key, Growl: gn })

            sendResponse('');
            return true;
        } else if (request.Type === 'NotificationClose') {
            if (!request.Key || !NotificationList.find(x => x.Key == request.Key)) {
                sendResponse('');
                return true;
            }

            let notificationIndex = NotificationList.findIndex(x => x.Key == request.Key)
            if (notificationIndex > -1) {
                notificationModel = NotificationList[notificationIndex]
                NotificationList.splice(notificationIndex, 1)
                notificationModel.Growl.close()

                //对于外部库引用类型,以防万一,手动释放.使用延时是因为Notification库在关闭时有延时,不能立刻赋空
                setTimeout(() => {
                    if (notificationModel && notificationModel.Growl)
                        notificationModel.Growl = null;
                    if (notificationModel)
                        notificationModel = null;
                }, 5000);
            }

            sendResponse('');
            return true;
        } else if (request.Type === 'ConfirmAcquisition') {

            GrowlNotification.notify({
                title: '无忧易售',
                description: request.Message,
                type: request.MessageType,
                position: 'top-center',
                closeTimeout: 0,
                closeWith: "button",
                image: { visible: true, customImage: config.logoBase64 },
                showButtons: true,
                buttons: {
                    action: {
                        text: '是',
                        callback: function () {
                            sendMessageToBackgroudScript({
                                "Type": "CollectionGoods",
                                "IsVerifyDuplicate": false,
                                "sourceUrl": request.Url
                            }, function (response) {
                            });
                        }
                    },
                    cancel: {
                        text: '否',
                        callback: function () {
                        }
                    }
                }
            });
            sendResponse('');
            return true;
        } else if (request.Type === 'RedirectSite') {
            ShowRedirectSiteBox(request.Message, request.MessageType, request.Site);
            sendResponse('');
            return true;
        } else if (request.Type === 'SaveKey') {//存储数据到网页中
            try {
                window[request.Key] = request.Value;
                if ($('[data-action="shopeebatch"]').length) {
                    $('[data-action="shopeebatch"]').click();
                }
            } catch (e) {
            }
            sendResponse('');
            return true;
        } else if (request.Type === 'CheckCollectionGoodsBtnDisabled') {
            if (request.Disabled && $("#51selling_collectiongoods") && $("#51selling_collectiongoods").length > 0) {
                if ($("#51selling_collectiongoods").text() != "处理中") {
                    $("#51selling_collectiongoods").attr({ "disabled": "disabled" });
                    $("#51selling_collectiongoods").text("处理中");
                }
            } else {
                if ($("#51selling_collectiongoods").text() == "处理中") {
                    $("#51selling_collectiongoods").removeAttr("disabled");
                    $("#51selling_collectiongoods").text("开始采集");
                }
            }

            sendResponse('');
            return true;
        } else if (request.Type === 'ShowTmallVerifyBox') {//天猫验证码展示
            if ($('#wyys-TmallVericodeModal').length <= 0) {
                let tmallVericodeModal = $('<div class="wyys-modal center middle" id="wyys-TmallVericodeModal">' +
                    '<div class="wyys-modal-dialog" style="width:500px;"><div class="wyys-modal-content" style="width:500px;margin-top:100px;">' +
                    '<div id="wyys-TmallVericodeModalContent" class="wyys-modal-body repeat-crawl-modal-content" style="padding:10px">' +
                    '</div></div></div>');

                $('<div></div>').append(tmallVericodeModal).appendTo('body');
            }

            let htmlStr = request.BoxHtml;
            $('#wyys-TmallVericodeModalContent').html(htmlStr);
            wyysModal.show('#wyys-TmallVericodeModal');

            sendResponse('');
            return true;
        } else if (request.Type === 'HideTmallVerifyBox') {//天猫验证码隐藏
            if ($('#wyys-TmallVericodeModal').length > 0) {
                $('#wyys-TmallVericodeModalContent').empty();
                wyysModal.hide('#wyys-TmallVericodeModal');
                GrowlNotification.notify({
                    title: '无忧易售',
                    description: "验证完成！请重新点击采集",
                    type: "success",
                    position: 'top-right',
                    closeTimeout: 3000,
                    image: { visible: true, customImage: config.logoBase64 },
                });

                //这里调用下接口，触发重新获取token
                try {
                    $.ajax({
                        url: "https://h5api.m.tmall.com/h5/mtop.taobao.pcdetail.data.get/1.0/?jsv=2.6.1&&appKey=12574478",
                        type: 'get',
                        async: true,
                        dataType: "html",
                        success: function (res) {
                        },
                        error: function (data, status, e) {
                        }
                    })
                } catch (e) {

                }

            }

            sendResponse('');
            return true;
        }
        else if (request.Type === 'ShowYandexVerifyBox') {
            //Yandex验证展示
            if ($('#wyys-YandexVericodeModal').length <= 0) {
                let yandexVericodeModal = $('<div class="wyys-modal center middle" id="wyys-YandexVericodeModal">' +
                    '<div class="wyys-modal-dialog" style="width:500px;"><div class="wyys-modal-content" style="width:500px;margin-top:100px;">' +
                    '<div id="wyys-YandexVericodeModalContent" class="wyys-modal-body repeat-crawl-modal-content" style="padding:10px">' +
                    '</div></div></div>');

                $('<div></div>').append(yandexVericodeModal).appendTo('body');
            }

            let htmlStr = request.BoxHtml;
            $('#wyys-YandexVericodeModalContent').html(htmlStr);
            wyysModal.show('#wyys-YandexVericodeModal');

            sendResponse('');
            return true;
        }
        else if (request.Type === 'HideYandexVerifyBox') {
            //Yandex验证码隐藏
            if ($('#wyys-YandexVericodeModal').length > 0) {
                $('#wyys-YandexVericodeModalContent').empty();
                wyysModal.hide('#wyys-YandexVericodeModal');
                GrowlNotification.notify({
                    title: '无忧易售',
                    description: "验证完成！请重新点击采集",
                    type: "success",
                    position: 'top-right',
                    closeTimeout: 3000,
                    image: { visible: true, customImage: config.logoBase64 },
                });

                // //这里调用下接口，触发重新获取token
                // try {
                //     $.ajax({
                //         url: "https://h5api.m.tmall.com/h5/mtop.taobao.pcdetail.data.get/1.0/?jsv=2.6.1&&appKey=12574478",
                //         type: 'get',
                //         async: true,
                //         dataType: "html",
                //         success: function (res) {
                //         },
                //         error: function (data, status, e) {
                //         }
                //     })
                // } catch (e) {

                // }
            }

            sendResponse('');
            return true;
        }
        else if (request.Type === 'CheckCategoryBtnDisabled') {
            if (request.Disabled && $("#51selling_collectioncategory") && $("#51selling_collectioncategory").length > 0) {
                if ($("#51selling_collectioncategory").text() != "处理中") {
                    $("#51selling_collectioncategory").attr({ "disabled": "disabled" });
                    $("#51selling_collectioncategory").text("处理中");
                }
            } else {
                if ($("#51selling_collectioncategory").text() == "处理中") {
                    $("#51selling_collectioncategory").removeAttr("disabled");
                    $("#51selling_collectioncategory").text("开始采集");
                }
            }

            sendResponse('');
            return true;
        } else if (request.Type === "AlibabaCategoryCrawl") {//1688类目采集产品id
            var pageNum = 0;
            if (request.pageNum) {
                pageNum = request.pageNum;
            }
            pageNum += 1;
            var pageSize = 30;
            if (request.data && request.data.length > 0) {
                Crawl.categoryDataList.push(...request.data);
                Crawl.categoryCrawlCountNum += request.data.length;
                $('.wyysTotalNum').text(Crawl.categoryCrawlCountNum);
            }
            if (request.totalCount) {
                Crawl.categoryCrawlTotalNum = request.totalCount;
            }
            //获取cookie
            var h5_tk = getCookie('_m_h5_tk')
            var contend = { token: h5_tk, pageNum: pageNum, url: window.location.href, next: '', platformId: 5 };
            if (window._LiSelling1688CatId_ !== undefined && window._LiSelling1688CatId_ !== undefined) {
                console.log(window._LiSelling1688CatId_);
                contend.catid = window._LiSelling1688CatId_;
            }
            if (pageNum == 1) {
                sendResponse(contend);
            } else if (pageNum > 1) {
                var maxPageNum = Crawl.categoryCrawlTotalNum > 0 ? Math.ceil(Crawl.categoryCrawlTotalNum / pageSize) : 0;
                if (maxPageNum > 0 ? pageNum <= maxPageNum : (Crawl.categoryCrawlTotalNum > Crawl.categoryCrawlCountNum || (request.data && request.data.length >= pageSize)))
                    contend.next = '1';

                contend.data = [];
                if (request.data && request.data.length > 0)
                    contend.data = request.data;
                sendResponse(contend);
            }
            return true;
        } else if (request.Type === "SetCategoryProgress") {//设置采集进度条
            var totalCount = Crawl.categoryCrawlTotalNum;
            $('.wyysTotalNum').text(totalCount);
            var $msgModal = $('#wyysCategoryCollectMsgModal');
            if (request.ProcessType === 1) {//重复采集
                Crawl.CarwlDetailExcuteNum += 1;
                Crawl.repeatDataList.push(request.data)
            } else if (request.ProcessType === 2) { //采集成功
                Crawl.CarwlDetailSuccessNum += 1;
                Crawl.CarwlDetailExcuteNum += 1;
            } else if (request.ProcessType === 3) {//采集失败
                var failCount = request.FillToTotal && totalCount > Crawl.CarwlDetailExcuteNum
                    ? totalCount - Crawl.CarwlDetailExcuteNum
                    : (request.Count > 0 ? request.Count : 1);
                Crawl.CarwlDetailErrorNum += failCount;
                Crawl.CarwlDetailExcuteNum += failCount;
                if (request.url)
                    Crawl.CarwlDetailErrorUrl.push(request.url);
            }

            $msgModal.find('.completionNum').text(Crawl.CarwlDetailExcuteNum);
            $msgModal.find('.wyys-f-blue').text(Crawl.CarwlDetailSuccessNum);
            $msgModal.find('.wyysFail').text(Crawl.CarwlDetailErrorNum);
            if (totalCount > 0) {
                $msgModal.find('.crawProgressBar').css('width', Math.min(Crawl.CarwlDetailExcuteNum / totalCount, 1) * 100 + '%')

            }
            sendResponse('');
            return true;
        } else if (request.Type === "SetCategoryResult") {
            if (Crawl.repeatDataList.length > 0) {
                Crawl.repeatDataList.forEach(function (item) {
                    var html = '<tr class="content"><td class="has-ipt">' +
                        '<input name="sourceUrlRepeat" type="checkbox" value="' + item.SourceUrl + '">' +
                        '</td><td class="img-box"><div class="img-out">' +
                        '<img class="imgCss" src="' + item.ImageUrl.split("|")[0] +
                        '" width="50px" height="50px"/></div></td>' +
                        '<td><a href="' + item.SourceUrl + '" target="_blank">' + item.Title + '</a></td></tr>';
                    $("#wyysCategoryCollectRepeatCrawlModal").find('#repeatValue').append(html);
                    $('#wyysCategoryCollectRepeatCrawlModal').find('input[name = "sourceUrlRepeat"]').prop('checked', false);
                })
                wyysModal.show("#wyysCategoryCollectRepeatCrawlModal");
            } else {
                //采集完成
                GrowlNotification.notify({
                    title: '无忧易售',
                    description: '采集完成',
                    type: 'Alter',
                    position: 'top-right',
                    closeTimeout: 3000,
                    image: { visible: true, customImage: config.logoBase64 },
                });
                ShowBottomMenu();
            }
            sendResponse('');
            return true;
        } else if (request.Type === "GetMercadoHtml") {
            try {
                if (isSameMercadoProductPage(request.RequestUrl, location.href, document)) {
                    sendResponse({ IsSuccess: true, Data: document.documentElement.outerHTML });
                    return true;
                }
            } catch (e) { }
            fetchWithCallback(request.RequestUrl, { method: 'GET' }, function (res) {
                if (res && res.success) {
                    sendResponse({ IsSuccess: true, Data: res.data });
                } else {
                    sendResponse({ IsSuccess: false, Data: res });
                }
            });
            return true;
        }
        else if (request.Type === "GetAjaxResult") {//请求接口，有些接口不适用于在backgroud里做请求，会有校验
            $.ajax({
                type: request.RequestMethod,
                headers: request.RequestHeaders,
                xhrFields: {
                    withCredentials: true
                },
                url: request.RequestUrl,
                async: request.Async ? true : false,
                contentType: request.RequestContentType,
                dataType: request.RequestDataType,
                data: request.RequestData,
                success: function (data) {
                    sendResponse({ IsSuccess: true, Data: data });
                },
                error: function (jqXHR, textStatus, errorThrown) {
                    sendResponse({ IsSuccess: false, Data: jqXHR });
                }
            });
            return true;
        } else if (request.Type === "GetDocumentCookies") {
            var resultData = {};
            for (var i = 0; i < request.NeedNameArr.length; i++) {
                resultData[request.NeedNameArr[i]] = getCookie(request.NeedNameArr[i]);
            }
            sendResponse(resultData);
            return true;
        } else if (request.Type === "GetOnbuyVariationsInfo") {
            let skuFirstImage = '';
            let price = 0;

            try {
                let dom = new DOMParser();
                let imageDoc = dom.parseFromString(request.HtmlStr, 'text/html');
                let imagesElement = imageDoc.querySelector("#image-gallery").querySelectorAll("a");
                skuFirstImage = imagesElement[0].attributes["href"].value;
                let priceString = imageDoc.querySelector(".q-p").querySelector(".price").innerText;
                price = parseFloat(priceString.replace(/[^\d.]/g, ''));
            } catch (e) { }

            sendResponse(
                {
                    SkuFirstImage: skuFirstImage,
                    Price: price
                });
            return true;
        } else if (request.Type === "GetOnbuyProductInfo") {
            let desc = '';
            let title = '';
            let categoryId = '';
            let categoryName = '';
            let productId = '';

            let skus = [];
            let parameters = [];
            let imageList = [];
            let propertyNames = [];

            let price = 0;
            let hasMoreSku = false;

            try {
                let parser = new DOMParser();
                let doc = parser.parseFromString(request.HtmlStr, 'text/html');
                title = doc.querySelectorAll(".product-name")[0].innerHTML;

                let cloneDescTag = doc.querySelector("#product-description").cloneNode(true);
                let descRights = cloneDescTag.querySelectorAll(".desc-right");
                descRights.forEach(function (el) {
                    if (el.textContent.includes("Details")) {
                        el.remove();//排除描述中的Details信息
                    }
                });
                desc = cloneDescTag.innerHTML.replace('Description & Details', 'Description').replace('Description &amp; Details', 'Description');

                let topModel = null;

                const scriptTag1 = doc.querySelector(".top-info");
                if (scriptTag1 && scriptTag1.querySelector('script') && scriptTag1.querySelector('script').textContent) {
                    topModel = JSON.parse(scriptTag1.querySelector('script').textContent)
                }
                else if (doc.querySelectorAll('script[type="application/ld+json"]').length > 0) {
                    const scripts = doc.querySelectorAll('script[type="application/ld+json"]');
                    const targetScript = Array.from(scripts).find(script =>
                        script.textContent.includes('itemListElement')
                    );

                    if (targetScript) {
                        const targetContent = targetScript.textContent;
                        topModel = JSON.parse(targetContent)
                    }
                }

                let divElement = doc.createElement('div');
                divElement.innerHTML = topModel.itemListElement[topModel.itemListElement.length - 2].name;
                categoryName = divElement.textContent;

                if (doc.querySelector(".product-features")) {
                    var lis = doc.querySelector(".product-features").querySelectorAll("li");
                    lis.forEach(element => {
                        var text = element.textContent.trim();
                        var match = text.match(/(.+):(.+)/);
                        if (match) {
                            var key = match[1].trim();
                            var value = match[2].trim();
                            if (!parameters.some(z => z.Key == key)) {
                                parameters.push({
                                    Key: key,
                                    Value: value,
                                });
                            }

                        }

                    })
                }

                categoryId = doc.querySelector(".product-code").attributes["data-category_id"].value;
                var priceString = doc.querySelector(".q-p").querySelector(".price").innerText;
                price = parseFloat(priceString.replace(/[^\d.]/g, ''));

                //产品主图
                var images = doc.querySelector("#image-gallery").querySelectorAll("a");
                images.forEach(element => {
                    imageList.push(element.attributes["href"].value)
                });

                if (doc.querySelector(".product-options div")) {
                    hasMoreSku = true;
                    productId = doc.querySelector(".product-options").attributes["data-product_id"].value;
                    let attributes = doc.querySelector(".product-options").querySelectorAll("div");
                    var properties = []
                    attributes.forEach(element => {
                        var name = element.querySelector("label").textContent;
                        propertyNames.push(name.replace(":", ""));
                        var options = element.querySelector("select").querySelectorAll("option");
                        var values = []
                        options.forEach(option => {
                            var id = option.attributes["value"].value;
                            if (id) {
                                values.push({ id: id, value: option.textContent });
                            }
                        })
                        properties.push({ key: name, value: values });
                    });
                    const match = title.match(/\(([^)]+)\)/);
                    const targetValues = []; // 存储从标题中解析出的目标值，按顺序
                    if (match) {
                        const bracketContent = match[1].trim();
                        targetValues.push(...bracketContent.split(',').map(part => part.trim()));
                    }
                    var setSku = function generateCombinations(properties) {
                        const combinations = [];
                        function helper(index, combination) {
                            if (index === properties.length) {
                                let matches = true;
                                // 遍历所有属性，检查是否与解析出的标题值匹配
                                for (let i = 0; i < properties.length; i++) {
                                    const attributeName = `attributeValue${i + 1}`;
                                    const expectedValue = targetValues[i]; // 从标题解析出的第 i 个值
                                    // 如果标题中的值数量不够，或者当前值不匹配，则整个组合不匹配
                                    if (expectedValue === undefined || combination[attributeName] !== expectedValue) {
                                        matches = false;
                                        break;
                                    }
                                }
                                if (matches)
                                    combination['imageUrl'] = imageList.join('|');
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
                                newCombination['price'] = price;
                                newCombination['imageUrl'] = '';
                                newCombination['hasStock'] = 0;
                                helper(index + 1, newCombination);
                            }
                        }

                        helper(0, {});

                        return combinations;
                    }

                    //多属性
                    skus = setSku(properties);
                    //拿到页面有库存的变体
                    doc.querySelector(".variant-list").querySelectorAll(".variant").forEach(element => {
                        var attributeLable = element.querySelectorAll(".detail");
                        var attributeValue1 = '';
                        var attributeValue2 = '';
                        if (attributeLable.length > 0) {
                            attributeValue1 = attributeLable[0].querySelector(".value").textContent;
                        }
                        if (attributeLable.length > 1 && attributeLable[1].querySelector(".value")) {
                            attributeValue2 = attributeLable[1].querySelector(".value").textContent;
                        }
                        for (i = 0; i < skus.length; i++) {
                            var sku = skus[i];
                            var attr1 = '';
                            var attr2 = '';
                            if (sku.attribute1Id) attr1 = sku.attributeValue1;
                            if (sku.attribute2Id) attr2 = sku.attributeValue2;
                            if (attributeValue1 == attr1 && attributeValue2 == attr2) {
                                skus[i].hasStock = 1;
                                break;
                            }
                        }
                    });
                }

            } catch (e) { }

            sendResponse(
                {
                    Title: title,
                    Desc: desc,
                    CategoryId: categoryId,
                    CategoryName: categoryName,
                    ProductId: productId,
                    Price: price,
                    HasMoreSku: hasMoreSku,
                    Skus: skus,
                    Parameters: parameters,
                    ImageList: imageList,
                    PropertyNames: propertyNames
                });
            return true;
        }
        else if (request.Type === 'GetFruugoProductInfo') {
            let desc = '';
            let categoryId = '';
            let categoryName = '';
            let otherSkuIds = [];
            let skus = [];
            let parameters = [];
            let propertyNames = [];
            let imageList = [];
            let price = 0;
            let currency = '';
            let skuAttr = [];
            let hasMoreSku = false;
            try {
                let parser = new DOMParser();
                let doc = parser.parseFromString(request.HtmlStr, "text/html");
                const skuInfo = extractAttributesAndValues(doc);
                var title = doc.querySelector('.js-product-title').innerHTML;
                const skuid = Number(
                    doc.querySelector('input[name="skuId"]').value
                );
                var descDiv = doc.querySelector("#description");
                desc = descDiv.querySelector("div:first-child").outerHTML;
                const lastItemLink = doc.querySelector(
                    "ol li:last-child a.breadcrumb__link"
                );

                try {
                    categoryName = lastItemLink.textContent.trim();
                    categoryId =
                        (lastItemLink.getAttribute("href").match(/\/a-(\d+)/) ||
                            [])[1] || "";
                } catch (e) { }

                // 选择所有属性列表项
                var spec = doc.querySelector(".product-description-spec-list");
                const items = spec.querySelectorAll("li");

                items.forEach((item) => {
                    const strong = item.querySelector("strong");
                    const valueElement = item.querySelector("a, span");
                    if (strong && valueElement) {
                        const key = strong.textContent.replace(":", "").trim();
                        const value = valueElement.textContent.trim();
                        parameters.push({ key, value });
                    }
                });
                // 获取图片 .Product__Gallery 元素
                let scripts = doc.querySelectorAll('script');
                let matchingScripts = Array.from(scripts).filter(script => script.textContent.includes('window.skuInfo'));
                if (matchingScripts.length > 0) {
                    let scriptContent = matchingScripts[0].textContent;
                    let jsonMatch = scriptContent.match(/window\.skuInfo\s*=\s*({.*?});/);

                    if (jsonMatch) {
                        // 解析 JSON 对象
                        let skuInfoJson = JSON.parse(jsonMatch[1]);
                        imageList = skuInfoJson.images.urls;
                        var attrs = skuInfoJson.attributes;
                        if (attrs && attrs.length > 1)
                            skuInfoJson.attributes.filter(item => item.type !== "OTHER");

                        skuAttr = attrs.map(item => ({
                            Key: item.title,
                            Value: item.value
                        }));
                    }
                }
                // 价格
                let pricemetaTag = doc.querySelector('meta[property="product:sale_price:amount"]');

                price = pricemetaTag ? pricemetaTag.getAttribute('content') : 0;

                if (!price) {
                    try {
                        const priceElement = doc.querySelector('.Product__Details p.price');
                        const priceContent = priceElement ? priceElement.textContent.trim() : '';
                        const numberStr = priceContent.match(/[\d.]+/)[0];
                        price = parseFloat(numberStr);
                    } catch (e) { }
                }

                if (!price || price === 0) {
                    pricemetaTag = doc.querySelector('meta[property="product:price:amount"]');
                    price = pricemetaTag ? pricemetaTag.getAttribute('content') : 0;
                }
                let currencyMetaTag = doc.querySelector('meta[property="product:sale_price:currency"]');
                if (!currencyMetaTag) {
                    currencyMetaTag = doc.querySelector('meta[property="product:price:currency"]');
                }
                currency = currencyMetaTag ? currencyMetaTag.getAttribute('content') : 'USD';

                if (skuInfo !== null) {
                    propertyNames = skuInfo.propertyName;
                    hasMoreSku = true;
                    //排除当前sku
                    otherSkuIds = skuInfo.uniqueIds.filter(
                        (item) => item !== skuid
                    );
                }
            } catch (e) { }
            sendResponse(
                {
                    Currency: currency,
                    Desc: desc,
                    CategoryId: categoryId,
                    CategoryName: categoryName,
                    Price: price,
                    HasMoreSku: hasMoreSku,
                    Skus: skus,
                    OtherSkuids: otherSkuIds,
                    Parameters: parameters,
                    ImageList: imageList,
                    PropertyNames: propertyNames,
                    SkuAttr: skuAttr,
                    Title: title
                });
            return true;
        } else if (request.Type === 'GetFruugoVariationsInfo') {
            let imageList = [];
            let price = 0;
            let currency = '';
            let skuAttr = [];
            try {
                let parser = new DOMParser();
                let doc = parser.parseFromString(request.HtmlStr, "text/html");
                const skuInfo = extractAttributesAndValues(doc);
                // 获取图片 .Product__Gallery 元素
                let scripts = doc.querySelectorAll('script');
                let matchingScripts = Array.from(scripts).filter(script => script.textContent.includes('window.skuInfo'));
                if (matchingScripts.length > 0) {
                    let scriptContent = matchingScripts[0].textContent;
                    let jsonMatch = scriptContent.match(/window\.skuInfo\s*=\s*({.*?});/);

                    if (jsonMatch) {
                        // 解析 JSON 对象
                        let skuInfoJson = JSON.parse(jsonMatch[1]);
                        imageList = skuInfoJson.images.urls;
                        var attrs = skuInfoJson.attributes;
                        if (attrs && attrs.length > 1)
                            skuInfoJson.attributes.filter(item => item.type !== "OTHER");

                        skuAttr = attrs.map(item => ({
                            Key: item.title,
                            Value: item.value
                        }));
                    }
                }
                // 价格
                let pricemetaTag = doc.querySelector('meta[property="product:sale_price:amount"]');

                price = pricemetaTag ? pricemetaTag.getAttribute('content') : 0;

                if (!price) {
                    try {
                        const priceElement = doc.querySelector('.Product__Details p.price');
                        const priceContent = priceElement ? priceElement.textContent.trim() : '';
                        const numberStr = priceContent.match(/[\d.]+/)[0];
                        price = parseFloat(numberStr);
                    } catch (e) { }
                }

                if (price === 0) {
                    pricemetaTag = doc.querySelector('meta[property="product:price:amount"]');
                    price = pricemetaTag ? pricemetaTag.getAttribute('content') : 0;
                }
                let currencyMetaTag = doc.querySelector('meta[property="product:sale_price:currency"]');
                if (!currencyMetaTag) {
                    currencyMetaTag = doc.querySelector('meta[property="product:price:currency"]');
                }
                currency = currencyMetaTag ? currencyMetaTag.getAttribute('content') : 'USD';
            } catch (e) { }
            sendResponse(
                {
                    Currency: currency,
                    Price: price,
                    ImageList: imageList,
                    SkuAttr: skuAttr
                });
            return true;
        }
        else if (request.Type === "GetBaoNiuNiuData") {
            let ph = "";
            let pid = "";
            let images = [];
            let atrbuts = [];
            let titlename = "";
            let cookie = "";
            let voideUrl = "";
            let discriptions = "";
            try {
                let parser = new DOMParser();
                let doc = parser.parseFromString(request.HtmlStr, "text/html");
                cookie = document.cookie;
                const element = doc.querySelector("#data-show");
                ph = element.getAttribute("data-hash");
                pid = element.getAttribute('data-product_id');
                titlename = doc.querySelector('.huohao').textContent;
                doc.querySelector('#thumblist').querySelectorAll("img").forEach(item => {
                    if (item.getAttribute("big") && item.getAttribute("big").indexOf(".gif") < 0)
                        images.push(item.getAttribute("big"));
                });
                doc.querySelector('#propshowbox').querySelectorAll("span").forEach(item => {
                    atrbuts.push(item.textContent);
                });
                if (cookie && cookie.indexOf("user_user_id") > -1) {
                    voideUrl = document.scripts[10].innerText
                }
                if (cookie && cookie.indexOf("user_user_id") > -1) {
                    discriptions = document.getElementById('productmemo').querySelector("p").textContent
                }

            } catch (e) {
                console.log(e)
            }
            sendResponse({ ph: ph, pid: pid, images: images, atrbuts: atrbuts, titlename: titlename, cookie: cookie, voideUrl: voideUrl, discriptions: discriptions });
        }
        else if (request.Type === "GetQingChuangData") {


            var content = "";
            if (document.querySelectorAll(".pro_detail .pro_img").length > 1) {
                content = document.querySelectorAll(".pro_detail .pro_img")[1].innerHTML;
            }



            // 创建一个临时 DOM 容器 
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = content;

            // 替换 lazyload 
            const lazyImages = tempDiv.querySelectorAll('img[lazyload]');
            lazyImages.forEach(img => {
                const lazySrc = img.getAttribute('lazyload');
                if (lazySrc) img.src = lazySrc;
            });

            content = tempDiv.innerHTML;
            if (document.getElementById("productProteryTmpl")) {
                document.getElementById("productProteryTmpl").remove();
            }
            if (document.getElementById("productContentTmpl")) {
                document.getElementById("productContentTmpl").remove();
            }
            if (document.getElementById("tradeRecListTmpl")) {
                document.getElementById("tradeRecListTmpl").remove();
            }




            // 获取所有颜色选项 
            const colorItems = document.querySelectorAll('.pro_color  li');
            const sku_arr = [];

            colorItems.forEach(colorItem => {
                const colorSpan = colorItem.querySelector('span');
                const colorEm = colorItem.querySelector('em');
                const color = (colorSpan ? colorSpan.textContent : (colorEm ? colorEm.textContent : '')).trim();

                // 获取对应的vid 
                const vid = colorItem.getAttribute('vid');

                // 找到对应vid的尺码容器 
                const sizeContainer = document.querySelector(`.pro_size[vid="${vid}"]`);
                //未登录
                if (content == "") {
                    var imgmodel = colorItem.querySelector('img');
                    // 获取图片地址（使用data-id中的大图）
                    const image = imgmodel ? imgmodel.getAttribute('data-id') : "";
                    var img_src = "";
                    if (image.indexOf("?") != -1) {

                        img_src = image.split('?')[0]

                    }
                    sku_arr.push({
                        index_image: img_src,
                        color: color
                    });
                    console.log(sku_arr);
                } else {


                    // 获取所有尺码项 
                    const sizeItems = sizeContainer.querySelectorAll('.pro_size_item  li');

                    sizeItems.forEach(sizeItem => {
                        // 获取尺码名称 
                        const size = sizeItem.querySelector('.size_name').textContent.trim();

                        // 获取价格 
                        const price = sizeItem.querySelector('.size_price').getAttribute('price');

                        var imgmodel = colorItem.querySelector('img');
                        // 获取图片地址（使用data-id中的大图）
                        const image = imgmodel ? imgmodel.getAttribute('data-id') : "";
                        var img_src = "";
                        if (image.indexOf("?") != -1) {

                            img_src = image.split('?')[0]

                        }
                        // 添加到结果数组 
                        sku_arr.push({
                            index_image: img_src,
                            color: color,
                            size: size,
                            price: price,

                        });

                    });



                }



            });
            console.log(sku_arr);



            const links = document.querySelectorAll('dd  a[data-big]');
            // 提取地址并拼接为字符串 
            const result = Array.from(links).map(a => a.getAttribute('data-big')).join('|'); console.log(result);

            let ph = "";
            let pid = "";
            let images = result;
            let atrbuts = [];
            let titlename = document.getElementsByClassName("toptitle")[0].innerText;
            let cookie = "";
            let voideUrl = $("#J_playVideo").attr("videourl");

            let discriptions = document.getElementsByClassName("pro_att")[0].innerHTML + content;


            let description = document.getElementsByClassName("pro_att")[0].innerText;

            let skus = sku_arr;
            // console.log(JSON.stringify(skus));


            sendResponse({ ph: ph, pid: pid, images: images, atrbuts: atrbuts, titlename: titlename, cookie: cookie, voideUrl: voideUrl, discriptions: discriptions, skus: skus, description: description });
        }
        else if (request.Type === "GetWestMonth") {
            sendResponse({ "isLinkCollect": true });
            return true;
        }
        else if (request.Type === "GetDouyinGoodStuff") {
            // 1. 提取商品价格   
            // 尝试从两个可能的 CSS 选择器中获取价格文本  
            var priceMatch1 = $(".activity-banner__price-info__price-area__left").text().match(/\d+(?:\.\d+)?/);
            var priceMatch2 = $(".price-line__price-container__price__amount").text().match(/\d+(?:\.\d+)?/);
            // 优先使用第一个匹配到的价格，否则使用第二个，若都未匹配则设为 "0"
            var price = priceMatch1 ? priceMatch1[0] : priceMatch2 ? priceMatch2[0] : "0";
            // 防止价格非数字的情况
            if (isNaN(Number(price))) {
                price = "0";
            }

            var imagelist = [];
            // 遍历轮播图中的每个滑块
            $(".swiper-wrapper .swiper-slide").each(function (index, element) {
                // 获取背景图的 style 属性
                var style = $(element).find("div").attr("style");
                if (style) {
                    // 从 style 字符串中解析出 URL
                    var urlStartIndex = style.indexOf("url(");
                    var imageUrl = style.slice(urlStartIndex + 5, -3); // 去掉 "url(" 和末尾的 ")"
                    if (imageUrl) {
                        imagelist.push(imageUrl);
                    }
                }
            });
            var attributes = [];
            // 遍历属性行
            $(".product-param__params__content__item__content__row").each(function (index, element) {
                attributes.push({
                    attrName: $(element).find(".product-param__params__content__item__content__row__key").text(),     // 属性名
                    attrValue: $(element).find(".product-param__params__content__item__content__row__value__desc__text").text() // 属性值
                });
            });
            sendResponse({ IsSuccess: true, Data: { price: price, title: $(".title-info__text").text(), description: $(".product-big-img-list").html(), imagelist: imagelist, attributes: attributes } });
        }
        else if (request.Type === 'GetSaleyeeProductInfo') {
            let desc = '';
            let categoryUrl = '';
            let categoryName = '';
            let skus = [];
            let parameters = [];
            let propertyNames = [];
            let imageList = [];
            let price = 0;
            let stockNum = 0;
            let currency = '';
            let skuAttr = [];
            let spuCode = '';
            let allProductIds = [];
            let productId = 0;
            let width2 = 0;
            let weight2 = 0;
            let height2 = 0;
            let length2 = 0;
            try {
                let parser = new DOMParser();
                let doc = parser.parseFromString(request.HtmlStr, "text/html");
                const skuInfoJson = doc.querySelector(".hideAttrListData").innerText;
                var title = doc.querySelector('.choose_h3').innerText.trim();
                var productInfo = JSON.parse(doc.querySelector(".hideDefaultSkuData").innerText);
                var skuId = '';
                if (productInfo && productInfo.ProductDetailRegionLogisticsProductList != null && productInfo.ProductDetailRegionLogisticsProductList.length > 0) {
                    var product = productInfo.ProductDetailRegionLogisticsProductList[0];
                    //库存
                    stockNum = product.StockQty;
                    if (product.ProductDetailLogisticsProductList && product.ProductDetailLogisticsProductList.length > 0) {
                        //价格
                        price = product.ProductDetailLogisticsProductList[0].Price_d;
                        currency = product.ProductDetailLogisticsProductList[0].Price.split(" ")[0];
                    }
                    skuId = productInfo.PlatformGoodsCode;
                    spuCode = productInfo.SPU;
                    productId = productInfo.Id,
                        title = productInfo.ProductNameUS;
                    width2 = productInfo.Spec.SpecWidth;
                    weight2 = productInfo.Spec.SpecWeight / 1000;
                    height2 = productInfo.Spec.SpecHeight;
                    length2 = productInfo.Spec.SpecLength;

                }
                // 获取图片 
                if (productInfo.PictureModels && productInfo.PictureModels.length > 0) {
                    imageList = productInfo.PictureModels.map(x => x.ImageUrl)
                }
                var attrs = doc.querySelectorAll('.li_attr');
                if (attrs && attrs.length > 0) {
                    //多属性
                    var skuInfos = JSON.parse(skuInfoJson);
                    allProductIds = [...new Set(skuInfos.map(x => x.PlatformGoodsCode))];
                    propertyNames = Array.from(attrs).map((attr) => attr
                        .querySelector("span")
                        .textContent.replace("：", "")
                        .trim())
                    // 获取所有属性的值
                    const attributes = Array.from(
                        attrs
                    ).map((attr) => {
                        const attrName = attr
                            .querySelector("span")
                            .textContent.replace("：", "")
                            .trim();
                        const attrCode = attr.getAttribute("data-attrcode");
                        const values = Array.from(
                            attr.querySelectorAll(".em_attr")
                        ).map((em) => ({
                            code: attrCode,
                            name: attrName,
                            value: em.getAttribute("data-attrval"),
                        }));
                        return { attrName, values };
                    });

                    // 生成笛卡尔积
                    function cartesianProduct(arr) {
                        return arr.reduce(
                            (acc, curr) => {
                                return acc.flatMap((d) =>
                                    curr.values.map((v) => [...d, { v }])
                                );
                            },
                            [[]]
                        );
                    }
                    // 获取 SKU 的笛卡尔积组合
                    const skuCombinations = cartesianProduct(attributes);
                    skuCombinations.forEach((item) => {
                        skus.push({
                            SkuId: '',
                            Price: price,
                            Property: item.map(item => ({
                                key: item.v.name,
                                value: item.v.value,
                                code: item.v.code
                            })),
                            Currency: currency,
                            VariantImageUrl: imageList[0],
                        });
                    });
                } else {
                    skus.push({
                        SkuId: skuId,
                        Price: price,
                        Property: [],
                        Currency: currency,
                        VariantImageUrl: imageList[0],
                    });
                }
                desc = doc.querySelector(".layui-tab-item").outerHTML;
                const lastItemLink = doc.querySelector(
                    ".location p a:last-of-type"
                );
                categoryName = lastItemLink.textContent.trim();
                categoryUrl = lastItemLink.href;
            } catch (e) { }
            sendResponse(
                {
                    allProductIds,
                    SpuCode: spuCode,
                    Currency: currency,
                    Desc: desc,
                    CategoryId: categoryUrl,
                    CategoryName: categoryName,
                    Price: price,
                    Skus: skus,
                    Parameters: parameters,
                    ImageList: imageList,
                    PropertyNames: propertyNames,
                    Title: title,
                    productId,
                    width2,
                    weight2,
                    height2,
                    length2
                });
            return true;
        } else if (request.Type === 'GetSaleyeeCategory') {
            let categoryId = 0
            try {
                let parser = new DOMParser();
                let doc = parser.parseFromString(request.HtmlStr, "text/html");
                var scriptText = doc.querySelector(".headtopmargin").querySelector("script").innerText;
                const cate3Match = scriptText.match(/cate3:\s*(\d+)/);
                categoryId = cate3Match ? parseInt(cate3Match[1], 10) : null;
            } catch (e) { }
            sendResponse({
                id: categoryId
            })
        } else if (request.Type === 'GetSaleyeeDesc') {
            let parser = new DOMParser();
            let doc = parser.parseFromString(request.HtmlStr, "text/html");
            doc.querySelector(".choose_description").innerHTML = request.desc;
            sendResponse({
                desc: doc.querySelector(".layui-tab-item").outerHTML
            })
        } else if (request.Type === 'GetJF91ProductInfo') {
            let goodsId = "";
            let specData = [];
            let dataIds = [];

            const parser = new DOMParser();
            const doc = parser.parseFromString(request.HtmlStr, 'text/html');

            const specDiv = doc.querySelector('div[name="init[]"][type="specs"]');
            const specContent = specDiv.textContent.trim();
            specData = JSON.parse(specContent);

            const goodsIdDiv = doc.querySelector('div[name="init[]"][type="goodsid"]');
            const goodsIdContent = goodsIdDiv.textContent.trim();
            goodsId = JSON.parse(goodsIdContent);

            const specPicListDiv = doc.querySelector('div.spec_pic_list');

            if (specPicListDiv) {
                // 在 spec_pic_list 内找到所有 sp_div 中的 a 标签，并提取 data-id 属性
                dataIds = Array.from(specPicListDiv.querySelectorAll('div.sp_div a[data-id]'))
                    .map(anchor => anchor.getAttribute('data-id')) // 提取 data-id 属性值
                    .filter((dataId, index, self) => self.indexOf(dataId) === index); // 去重
            }

            let data = {
                goodsId: goodsId,
                specs: specData,
                dataIds
            }
            sendResponse({ IsSuccess: true, Data: data });
        } else if (request.Type === "GetTiktokData") {
            // console.log("request.HtmlStr", request.HtmlStr);
            let resData = null;

            try {
                const doc = new DOMParser().parseFromString(request.HtmlStr, 'text/html');
                const element = doc.querySelector("#__MODERN_ROUTER_DATA__");
                if (!element) return null;

                const jsonObj = element.innerText;
                const loaderData = JSON.parse(jsonObj).loaderData;

                // 方案1：直接路径
                const directPaths = [
                    "(name$)/(id)/page",
                    "(shop$)/(pdp)/(name$)/(id)/page"
                ];

                for (const path of directPaths) {
                    try {
                        const data = loaderData[path]?.initialData?.productInfo;
                        if (data) {
                            resData = data;
                            break;
                        }
                    } catch { }
                }

                // 方案2：components_map 结构
                if (!resData) {
                    const componentPaths = [
                        "shop/pdp/(product_name_slug$)/(product_id)/page",
                        "shop/(region)/pdp/(product_name_slug$)/(product_id)/page",
                        "(region)/pdp/(product_name_slug$)/(product_id)/page",
                        "(product_name_slug$)/(product_id)/page"
                    ];

                    for (const path of componentPaths) {
                        try {
                            const components = loaderData[path]?.page_config?.components_map;
                            if (!components) continue;

                            const productInfo = components.find(x => x.component_name === "product_info")
                                ?.component_data?.product_info;

                            if (productInfo) {
                                resData = productInfo;
                                break;
                            }
                        } catch { }
                    }
                }

            } catch (e) {
                console.error("解析失败:", e);
            }


            sendResponse(
                {
                    data: resData
                });

            return true;

        }
        else if (request.Type === "CleanHtmlKeepTags") {
            sendResponse({
                data: cleanHtmlKeepTags(request.HtmlStr)
            });

            return true;
        }
        else if (request.Type === "GetYandexProductInfo") {
            let resData = {};
            let variantArr = [];
            //console.log("request.HtmlStr", request.HtmlStr);
            let dom = new DOMParser();
            let doc = dom.parseFromString(request.HtmlStr, 'text/html');

            try {
                const content = Array.from(doc.querySelectorAll('noframes[data-apiary="patch"]'))
                    .find(tag => {
                        const text = tag.textContent || tag.innerHTML;
                        return text.includes("oskuId") && text.includes("businessId");
                    })
                    ?.textContent || "";

                if (content && content != "") {
                    let contentObj = JSON.parse(content);
                    //console.log("contentObj", content);
                    let argument = {};
                    try {
                        argument = contentObj.widgets["@light/ToggleWishlist"]["/content/page/fancyPage/defaultPage/wishlist/wishlistToggle"];
                    } catch (e) {
                        // 找到第一个符合条件的 params
                        argument = Object.values(contentObj.collections.transition).find(
                            item => item.params?.businessId && item.params?.oskuId
                        )?.params;
                    }

                    const paths = [
                        "/content/page/fancyPage/wishlist/wishlistToggle",
                        "/content/page/content/defaultPage/wishlist/wishlistToggle"
                    ];

                    if (!argument) {
                        for (const path of paths) {
                            try {
                                argument = contentObj.widgets["@light/ToggleWishlist"][path];
                                if (argument) break;
                            } catch (e) { }
                        }
                    }

                    resData.CardBusinessId = argument.businessId;
                    resData.CardOskuId = argument.oskuId;
                    resData.CardProductId = argument.productId;
                }
            } catch (e) { }

            //获取变体Id数据方法1
            try {
                let dom = new DOMParser();
                let doc = dom.parseFromString(request.HtmlStr, 'text/html');
                let noframesElements = doc.querySelectorAll('noframes[data-apiary="patch"]');
                let matchedElement = Array.from(noframesElements).find(element => {
                    // return element.innerHTML.includes('productCardJumpTableValues');
                    return element.innerHTML.includes('UniversalPromoBadge');
                });
                let jsonData = JSON.parse(matchedElement.textContent.trim());
                console.log("jsonData", matchedElement.textContent.trim());

                let productCardJumpTableValues = jsonData.collections.productCardJumpTableValues;
                for (const key in productCardJumpTableValues) {
                    if (productCardJumpTableValues.hasOwnProperty(key)) {
                        let oskuIdTT = productCardJumpTableValues[key];
                        try {

                            let oskuId = productCardJumpTableValues[key].transition.params.oskuId;
                            let type = productCardJumpTableValues[key].type;
                            //2026-01-27发现请求不携带pagehref也可以调通
                            if (type == "image") {
                                variantArr.push({
                                    pagehref: "",
                                    oskuid: oskuId,
                                    type: type
                                });
                            }
                        } catch (e) { }
                    }
                }
            } catch (e) { }

            //获取变体Id数据方法2
            if (variantArr.length <= 0) {
                try {
                    const childDivs = doc.querySelectorAll('div._3kKKK._16UZQ > div') || [];
                    const resultArr = Array.from(childDivs).map(div => {
                        return {
                            filtername: div.getAttribute('filtername') || '',
                            type: div.getAttribute('type') || '',
                            oskuid: div.getAttribute('oskuid') || '',
                            skuid: div.getAttribute('skuid') || '',
                            id: div.getAttribute('id') || '',
                            pagehref: div.getAttribute('pagehref') || '',
                            value: div.getAttribute('value') || ''
                        };
                    });
                    variantArr = resultArr;
                } catch (e) { }
            }

            //获取变体Id数据方法3
            if (variantArr.length <= 0) {
                try {
                    const childDivs = doc.querySelectorAll('div._3kKKK > div') || [];
                    const resultArr = Array.from(childDivs).map(div => {
                        return {
                            filtername: div.getAttribute('filtername') || '',
                            type: div.getAttribute('type') || '',
                            oskuid: div.getAttribute('oskuid') || '',
                            skuid: div.getAttribute('skuid') || '',
                            id: div.getAttribute('id') || '',
                            pagehref: div.getAttribute('pagehref') || '',
                            value: div.getAttribute('value') || ''
                        };
                    });
                    variantArr = resultArr;
                } catch (e) { }
            }

            //获取变体Id数据方法4
            if (variantArr.length <= 0) {
                try {
                    const chipButtons = doc.querySelectorAll('#ChipListRow a[role="button"]') || [];
                    const resultArr = Array.from(chipButtons)
                        .map(a => a.getAttribute('href') || '')
                        .filter(href => href)   // 只保留包含 OskuId 的
                        .map(href => {

                            // 去掉参数部分
                            const path = href.split('?')[0];

                            // 取最后一段路径
                            const parts = path.split('/');
                            const oskuid = parts[parts.length - 1];

                            return {
                                pagehref: href,
                                oskuid: oskuid
                            };
                        });

                    variantArr = resultArr;
                } catch (e) { }
            }

            //获取变体Id数据方法5
            if (variantArr.length <= 0) {
                try {
                    const chipButtons = doc.querySelectorAll('._3Jybh a[role="button"]') || [];
                    const resultArr = Array.from(chipButtons)
                        .map(a => a.getAttribute('href') || '')
                        .filter(href => href)   // 只保留包含 OskuId 的
                        .map(href => {

                            // 去掉参数部分
                            const path = href.split('?')[0];

                            // 取最后一段路径
                            const parts = path.split('/');
                            const oskuid = parts[parts.length - 1];

                            return {
                                pagehref: href,
                                oskuid: oskuid
                            };
                        });

                    variantArr = resultArr;
                } catch (e) { }
            }

            //排除oskuid='#'且根据oskuid去重
            function filterAndUnique(arr) {
                const map = new Map();

                return arr.filter(item => {
                    // 1. 只保留 oskuid 等于 '#' 的对象
                    if (item.oskuid == '#') return false;

                    // 2. 利用 Map 的特性进行去重
                    if (!map.has(item.oskuid)) {
                        map.set(item.oskuid, true);
                        return true;
                    }
                    return false;
                });
            }
            variantArr = filterAndUnique(variantArr);

            sendResponse({ data: resData, variantArr });
            return true;
        }
        else if (request.Type === "GetYandexData") {
            let resData = {};
            // try {
            //     console.log(request.HtmlStr);

            //     let matchSk = request.HtmlStr.match(/"sk":"([^"]+)"/);

            //     if (matchSk) {
            //         let skValue = matchSk[1];  // match[1] 是捕获的 sk 值
            //         console.log("sk 的值是:", skValue);
            //     } else {
            //         console.log("未找到 sk 的值");
            //     }

            //     let dom = new DOMParser();
            //     let doc = dom.parseFromString(request.HtmlStr, 'text/html');
            //     let noframesElements = doc.querySelectorAll('noframes[data-apiary="patch"]');
            //     let matchedElement = Array.from(noframesElements).find(element => {
            //         return element.innerHTML.includes('/content/page/fancyPage/defaultPage/productRating');
            //     });
            //     let jsonData = JSON.parse(matchedElement.textContent.trim());

            //     // let element = doc.querySelector(".disableOverscroll");
            //     // let zoneData = element ? element.getAttribute("data-zone-data") : null;
            //     // let productData1 = JSON.parse(zoneData);

            //     productData2 = jsonObj;
            // } catch (e) {}

            try {
                $.ajax({
                    url: "https://market.yandex.ru/manifest.json",
                    method: 'GET',
                    async: false, // 异步请求
                    success: function (html) {
                    },
                    error: function (jqXHR, textStatus, errorThrown) {
                        console.log(`Error fetching`, jqXHR);
                        let responseText = jqXHR.responseText;
                        console.log(`responseText`, responseText);

                        const regex = /window\.state\s*=\s*(\{.*\});/;
                        const match = responseText.match(regex);
                        if (match) {
                            resData = JSON.parse(match[1]);
                            console.log(resData);
                        } else {
                            console.log("Yandex未找到有效的对象");
                        }
                    }
                });
            } catch (e) { }

            sendResponse({ data: resData });
            return true;

        }
        else if (request.Type === "GetSheinPagePrice") {
            let price = "0";
            let dom = new DOMParser();
            let doc = dom.parseFromString(request.HtmlStr, 'text/html');
            try {
                price = doc.getElementById("productMainPriceId").innerText;
            } catch (e) { }

            sendResponse({ price });
            return true;
        }
        else if (request.Type === "GetAliexpressRuData") {
            var paraObj = request.Paras;
            let skuInfo = "";
            const descUrl = `https://aliexpress.ru/aer-jsonapi/v1/bx/pdp/web/productData?productId=${paraObj.productId}&sourceId=${paraObj.sourceId}&sku_id=${paraObj.skuId}`;
            try {
                $.ajax({
                    url: descUrl,
                    method: 'GET',
                    dataType: 'text', // Specify that we expect text data
                    async: false, // Note: Using synchronous requests is deprecated
                    success: function (data) {
                        skuInfo = data;
                        sendResponse({ skuInfo });
                    },
                    error: function (jqXHR, textStatus, errorThrown) {
                        sendResponse({ skuInfo });
                    }
                });
            } catch (e) {
                sendResponse({ skuInfo });
            }
        }
        else if (request.Type === "GetBanggoodProductLanguage") {
            let dom = new DOMParser();
            let document = dom.parseFromString(request.HtmlStr, 'text/html');
            let language = "en-GB";
            const items = document.getElementsByName("header-submit");
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                const data = item.getAttribute("data-hinit-search");
                if (data) {
                    const value = data.split("|");
                    if (value.length > 1) { // 因为要取倒数第二个
                        language = value[value.length - 2];
                    }
                }
            }

            sendResponse(
                {
                    data: language
                });

            return true;
        }
        else if (request.Type === "CheckPinDuoDuoProductInfo") {
            // 解析 HTML 字符串
            let dom = new DOMParser();
            let document2 = dom.parseFromString(request.HtmlStr, 'text/html');

            // 获取所有 script 标签
            const scripts = document2.getElementsByTagName("script");

            // 默认 true，如果找到且不是 null 再改为 false
            let rawDataIsNull = true;

            for (let script of scripts) {
                const content = script.textContent || "";
                if (content.includes("window.rawData=")) {
                    // 提取 window.rawData= 后面的值
                    const match = content.match(/window\.rawData\s*=\s*(.*?);/);
                    if (match) {
                        const value = match[1].trim();
                        if (value !== "null") {
                            rawDataIsNull = false; // 找到并且不是 null
                        }
                    }
                    break; // 找到第一个 window.rawData= 就可以停止
                }
            }

            if (!rawDataIsNull) {
                sendResponse(
                    {
                        data: request.HtmlStr
                    });
                return true;
            }
            const extractGood = extractGoodsId(request.SouceUrl);
            $.ajax({
                type: "GET",
                url: extractGood.newUrl,
                async: false,
                contentType: "application/json",
                dataType: "text",
                success: function (html) {
                    console.log("html", html);
                    sendResponse(
                        {
                            data: html
                        });
                },
                error: function (results) {
                    sendResponse(
                        {
                            data: "",
                        });
                }
            });
        }
        else if (request.Type === "GetPinDuoDuoSkuInfo") {
            let userId = getCookie('pdd_user_id');
            let currentUrl = new URL(location.href);
            fetch(`/proxy/api/api/oak/integration/render/sku?pdduid=${userId}`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    page_version: 7,
                    _component_version: 2,
                    hostname: currentUrl.hostname,
                    front_supports: ["front_promo_price", "sku_selector_toast", "group_tip_end_time", "custom_sku", "goods_reminder", "morgan_suffix", "goods_reminder_click"],
                    goods_id: currentUrl.searchParams.get("goods_id"),
                    page_from: 0,
                    _oak_stage: "mall_page"
                })
            })
                .then(response => response.json())
                .then(response => {
                    sendResponse(
                        {
                            data: response
                        });
                })
                .catch(response => {
                    sendResponse(
                        {
                            data: "",
                        });
                });

            return true;
        }
        else if (request.Type === "GetOnbuyPageHtml") {
            $.ajax({
                type: "GET",
                url: request.SouceUrl,
                async: false,
                contentType: "application/json",
                dataType: "text",
                success: function (html) {
                    sendResponse(
                        {
                            data: html
                        });
                },
                error: function (results) {
                    sendResponse(
                        {
                            data: "",
                        });
                }
            });
        }
        else if (request.Type === "GetMercadoPageData") {
            let dom = new DOMParser();
            let htmlDoc = dom.parseFromString(request.HtmlStr, 'text/html');
            //console.log(request.HtmlStr);
            let scripts = htmlDoc.getElementsByTagName("script");
            let model = null;
            for (let item of scripts) {
                // 1. 新情况，数据直接在 script 标签里
                if (item.id === "__NORDIC_RENDERING_CTX__" && item.innerHTML.includes("initialState")) {
                    let scriptContent = item.innerHTML.trim();
                    if (scriptContent) {
                        try {
                            let originalModel = JSON.parse(scriptContent);
                            model = originalModel.pageState;
                        } catch (e) {
                            console.error("JSON parse error (new case):", e);
                        }
                    }

                    //新情况2
                    if (model == null && scriptContent) {
                        let scriptContent = item.innerHTML.trim();
                        try {
                            const match = scriptContent.match(/_n\.ctx\.r\s*=\s*({.*?});/s);
                            if (match && match[1]) {
                                let jsonStr = match[1];
                                jsonStr = jsonStr.replace(/new Set\((\[.*?\])\)/g, '$1');
                                let scriptObj = JSON.parse(jsonStr, (key, value) => {
                                    return value;
                                });

                                model = scriptObj.appProps.pageProps;

                                break;
                            } else {
                                console.error("未找到 _n.ctx.r 对象");
                            }
                        } catch (e) {
                            console.error("解析失败:", e);
                        }
                    }

                }
                // 2. 旧情况，window.__PRELOADED_STATE__ = {...};
                else if (item.innerHTML.includes("window.__PRELOADED_STATE__ =")) {
                    let json = item.innerHTML.split("window.__PRELOADED_STATE__ =")[1];
                    if (json) {
                        let spitIndexdb = json.indexOf("}};");
                        let spitIndexfi = json.indexOf("};");
                        let spitIndex = spitIndexfi;

                        if ((spitIndexdb > 0 && spitIndexdb < spitIndexfi) || spitIndexdb < 0) {
                            spitIndexfi = spitIndexdb;
                        }

                        if (collectBox.Box.SourceUrl.includes("mercadolivre.com.br")) {
                            spitIndex += 1;
                        }

                        let jsonStr = json.substring(1, spitIndex).trimEnd(";");

                        if (jsonStr) {
                            try {
                                model = JSON.parse(jsonStr);
                            } catch (e) {
                                console.error("JSON parse error (old case):", e);
                            }
                        }
                    }
                }
            }
            console.log("model", JSON.stringify(model));
            sendResponse({ model });
        }
        else if (request.Type === "GetMercadoVariantData") {
            let requestUrl = request.PermaLink;
            if (!requestUrl) {
                requestUrl = updateMercadoUrlWithColor(request.SouceUrl, request.AttrId, request.ColorName);
            }

            let variantImages = [];

            $.ajax({
                type: "GET",
                url: requestUrl,
                async: false,
                contentType: "application/json",
                dataType: "text",
                success: function (html) {
                    try {
                        console.log(html);

                        let dom = new DOMParser();
                        let htmlDoc = dom.parseFromString(html, 'text/html');
                        let scripts = htmlDoc.getElementsByTagName("script");
                        let model = null;

                        for (let item of scripts) {
                            // 1. 新情况，数据直接在 script 标签里
                            if (item.id === "__NORDIC_RENDERING_CTX__" && item.innerHTML.includes("initialState")) {
                                let scriptContent = item.innerHTML.trim();
                                if (scriptContent) {
                                    try {
                                        let originalModel = JSON.parse(scriptContent);
                                        model = originalModel.pageState;
                                    } catch (e) { }
                                }

                                //新情况2
                                if (model == null && scriptContent) {
                                    let scriptContent = item.innerHTML.trim();
                                    try {
                                        const match = scriptContent.match(/_n\.ctx\.r\s*=\s*({.*?});/s);
                                        if (match && match[1]) {
                                            let jsonStr = match[1];
                                            jsonStr = jsonStr.replace(/new Set\((\[.*?\])\)/g, '$1');
                                            let scriptObj = JSON.parse(jsonStr, (key, value) => {
                                                return value;
                                            });

                                            model = scriptObj.appProps.pageProps;
                                            break;
                                        } else {
                                            console.error("未找到 _n.ctx.r 对象");
                                        }
                                    } catch (e) {
                                        console.error("解析失败:", e);
                                    }
                                }
                            }
                            // 2. 旧情况，window.__PRELOADED_STATE__ = {...};
                            else if (item.innerHTML.includes("window.__PRELOADED_STATE__ =")) {
                                let json = item.innerHTML.split("window.__PRELOADED_STATE__ =")[1];
                                if (json) {
                                    let spitIndexdb = json.indexOf("}};");
                                    let spitIndexfi = json.indexOf("};");
                                    let spitIndex = spitIndexfi;

                                    if ((spitIndexdb > 0 && spitIndexdb < spitIndexfi) || spitIndexdb < 0) {
                                        spitIndexfi = spitIndexdb;
                                    }

                                    if (collectBox.Box.SourceUrl.includes("mercadolivre.com.br")) {
                                        spitIndex += 1;
                                    }

                                    let jsonStr = json.substring(1, spitIndex).trimEnd(";");

                                    if (jsonStr) {
                                        model = JSON.parse(jsonStr);
                                    }
                                }
                            }
                        }

                        let imgTempConfig = model.initialState.components.picture_config.template_2x;
                        let pictruesObj = model.initialState.components.fixed;
                        if (!pictruesObj)
                            pictruesObj = model.initialState.components;

                        let picturesList = pictruesObj.gallery.pictures;
                        for (let i = 0; i < picturesList.length; i++) {
                            let pic = picturesList[i];
                            if (pic.id != null) {
                                let picPath = imgTempConfig.replace("{id}", pic.id);
                                variantImages.push(picPath);
                            }
                        }

                        sendResponse({ data: variantImages });

                    } catch (e) {
                        sendResponse({ data: variantImages });
                    }
                },
                error: function (results) {
                    sendResponse({ data: variantImages });
                }
            });


            // fetchWithCallback(requestUrl, {}, function (result) {
            //     if (result.success) {
            //         console.log('变体数据：', result.data);
            //         try {
            //             let dom = new DOMParser();
            //             console.log(result.data);
            //             let htmlDoc = dom.parseFromString(result.data, 'text/html');
            //             let scripts = htmlDoc.getElementsByTagName("script");
            //             let model = null;

            //             for (let item of scripts) {
            //                 // 1. 新情况，数据直接在 script 标签里
            //                 if (item.id === "__NORDIC_RENDERING_CTX__" && item.innerHTML.includes("initialState")) {
            //                     let scriptContent = item.innerHTML.trim();
            //                     if (scriptContent) {
            //                         try {
            //                             let originalModel = JSON.parse(scriptContent);
            //                             model = originalModel.pageState;
            //                         } catch (e) { }
            //                     }

            //                     //新情况2
            //                     if (model == null && scriptContent) {
            //                         let scriptContent = item.innerHTML.trim();
            //                         try {
            //                             const match = scriptContent.match(/_n\.ctx\.r\s*=\s*({.*?});/s);
            //                             if (match && match[1]) {
            //                                 let jsonStr = match[1];
            //                                 jsonStr = jsonStr.replace(/new Set\((\[.*?\])\)/g, '$1');
            //                                 let scriptObj = JSON.parse(jsonStr, (key, value) => {
            //                                     return value;
            //                                 });

            //                                 model = scriptObj.appProps.pageProps;
            //                                 break;
            //                             } else {
            //                                 console.error("未找到 _n.ctx.r 对象");
            //                             }
            //                         } catch (e) {
            //                             console.error("解析失败:", e);
            //                         }
            //                     }
            //                 }
            //                 // 2. 旧情况，window.__PRELOADED_STATE__ = {...};
            //                 else if (item.innerHTML.includes("window.__PRELOADED_STATE__ =")) {
            //                     let json = item.innerHTML.split("window.__PRELOADED_STATE__ =")[1];
            //                     if (json) {
            //                         let spitIndexdb = json.indexOf("}};");
            //                         let spitIndexfi = json.indexOf("};");
            //                         let spitIndex = spitIndexfi;

            //                         if ((spitIndexdb > 0 && spitIndexdb < spitIndexfi) || spitIndexdb < 0) {
            //                             spitIndexfi = spitIndexdb;
            //                         }

            //                         if (collectBox.Box.SourceUrl.includes("mercadolivre.com.br")) {
            //                             spitIndex += 1;
            //                         }

            //                         let jsonStr = json.substring(1, spitIndex).trimEnd(";");

            //                         if (jsonStr) {
            //                             model = JSON.parse(jsonStr);
            //                         }
            //                     }
            //                 }
            //             }

            //             let imgTempConfig = model.initialState.components.picture_config.template_2x;
            //             let pictruesObj = model.initialState.components.fixed;
            //             if (!pictruesObj)
            //                 pictruesObj = model.initialState.components;

            //             let picturesList = pictruesObj.gallery.pictures;
            //             for (let i = 0; i < picturesList.length; i++) {
            //                 let pic = picturesList[i];
            //                 if (pic.id != null) {
            //                     let picPath = imgTempConfig.replace("{id}", pic.id);
            //                     variantImages.push(picPath);
            //                 }
            //             }

            //             sendResponse({ data: variantImages });

            //         } catch (e) {
            //             sendResponse({ data: variantImages });
            //         }
            //     } else {
            //         sendResponse({ data: variantImages });
            //     }
            // });
            return true;
        }
        else if (request.Type === "GetDoba") {
            const parser = new DOMParser();
            let domhtml = parser.parseFromString(request.HtmlStr, 'text/html');
            const nextDataScript = domhtml.getElementById('__NEXT_DATA__');
            var rawData = JSON.parse(nextDataScript.textContent); 
            const productData = rawData.props.pageProps;
            const productDetail = productData.productDetail || {};
            const detail = productDetail.productDetail || {};//图文详情
            const packaging = productDetail.packaging || {};//尺寸信息
            const highlights = productDetail.highlights || {};//简介
            const allVariants = productDetail.allVariants || {};//变体集合
            const productName = productDetail.goodsName || document.title.split('-')[0].trim();
            const previewImageUrls = (productDetail.goodsImg || []) 
                .map(img => normalizeImageUrl(img.imgUrl || img.imgBigUrl))
                .filter(Boolean);
            const video = productDetail.selectedSku.videoMediaUrl;
            var model = {
                detail,
                packaging,
                highlights: highlights.join(),
                allVariants,
                productName,
                previewImageUrls: previewImageUrls,
                video
            };
            sendResponse({ model });
        }
        else if (request.Type === "GetMiravia") {
            const parser = new DOMParser();
            const doc = parser.parseFromString(request.HtmlStr, 'text/html');
            let moduleData = null;
            const scriptTags = doc.querySelectorAll('script');
            for (const script of scriptTags) {
                if (script.textContent.includes('__moduleData__')) {
                    const match = script.textContent.match(/__moduleData__\s*=\s*(\{[\s\S]*?\});/);
                    if (match && match[1]) {
                        moduleData = JSON.parse(match[1]);
                        break; // 找到后退出循环
                    }
                }
            }
            if (!moduleData)
                throw new Error("采集被拦截，请刷新当前页面进行验证！");

            const root = moduleData.data.root.fields;
            // 基础SKU信息
            const skuBase = root.productOption?.skuBase;
            if (!skuBase) return [];

            const properties = skuBase.properties || [];
            const skus = skuBase.skus || [];
            const productInfo = root.product || {};

            // 价格和图片信息
            const skuInfos = root.skuInfos || {};
            const skuGalleries = root.skuGalleries?.skuInfo || {};
            const imgs = [];

            // 为每个属性建立 vid → 显示名称 的映射，并收集所有可能的vid
            const propMaps = {};
            const propValueList = []; // 存储每个属性的pid和所有vid
            let colorPid = null; // 记录颜色属性的pid
            properties.forEach(prop => {
                const map = {};
                const values = [];
                (prop.values || []).forEach(val => {
                    map[val.vid] = val.name;
                    values.push(val.vid);
                });
                propMaps[prop.pid] = {
                    name: prop.name,
                    map: map,
                    values: values
                };
                propValueList.push({
                    pid: prop.pid,
                    values: values
                });
                // 识别颜色属性：如果属性值中包含图片，则视为颜色属性
                if (!colorPid && (prop.values || []).some(val => val.image)) {
                    colorPid = prop.pid;
                }
            });

            // 生成所有属性值的笛卡尔积
            function cartesianProduct(arrays) {
                return arrays.reduce((acc, curr) => {
                    return acc.flatMap(a => curr.map(b => [...a, b]));
                }, [[]]);
            }
            const allValueCombinations = cartesianProduct(propValueList.map(p => p.values));

            // 构建组合映射：key为propPath，value为包含property、预留price和img的对象
            const combinationMap = new Map();
            allValueCombinations.forEach(combination => {
                const propPath = combination.map((vid, index) => `${propValueList[index].pid}:${vid}`).join(';');
                const property = {};
                combination.forEach((vid, index) => {
                    const prop = propValueList[index];
                    const propInfo = propMaps[prop.pid];
                    property[propInfo.name] = propInfo.map[vid] || vid;
                });
                combinationMap.set(propPath, { property: property, price: '', img: '' });
            });

            // 构建颜色图片和价格映射：对于每个颜色vid，收集存在的SKU中该颜色的第一张图片和第一个价格
            const colorImgMap = new Map();
            const colorPriceMap = new Map();
            if (colorPid) {
                skus.forEach(sku => {
                    const propPath = sku.propPath;
                    // 从propPath中提取颜色vid
                    const pairs = propPath.split(';');
                    let colorVid = null;
                    for (let pair of pairs) {
                        const [pid, vid] = pair.split(':');
                        if (pid === colorPid) {
                            colorVid = vid;
                            break;
                        }
                    }
                    if (colorVid) {
                        const skuId = sku.skuId;
                        // 图片映射（取第一张）
                        const gallery = skuGalleries[skuId];
                        if (gallery && gallery.length > 0 && !colorImgMap.has(colorVid)) {
                            colorImgMap.set(colorVid, gallery[0].src);
                        }
                        // 价格映射（取第一个价格）
                        const priceObj = skuInfos[skuId]?.price?.salePrice;
                        if (priceObj && !colorPriceMap.has(colorVid)) {
                            colorPriceMap.set(colorVid, priceObj.priceText);
                        }
                    }
                });
            }

            // 遍历真实SKU，填充价格和图片
            skus.forEach(sku => {
                const propPath = sku.propPath;
                const entry = combinationMap.get(propPath);
                if (entry) {
                    const skuId = sku.skuId;
                    const priceObj = skuInfos[skuId]?.price?.salePrice;
                    entry.price = priceObj ? priceObj.priceText : '';
                    const gallery = skuGalleries[skuId];
                    if (gallery && gallery.length > 0) {
                        entry.img = gallery[0].src;
                        imgs.push(gallery[0].src); // 保持原有收集逻辑
                    }
                }
            });

            // 补充缺失的图片和价格：对于没有img或price的组合，尝试用同颜色的图片和价格填充
            if (colorPid) {
                for (let [propPath, value] of combinationMap.entries()) {
                    // 如果图片或价格缺失
                    if (!value.img || !value.price) {
                        // 从propPath中提取颜色vid
                        const pairs = propPath.split(';');
                        for (let pair of pairs) {
                            const [pid, vid] = pair.split(':');
                            if (pid === colorPid) {
                                if (!value.img && colorImgMap.has(vid)) {
                                    value.img = colorImgMap.get(vid);
                                }
                                if (!value.price && colorPriceMap.has(vid)) {
                                    value.price = colorPriceMap.get(vid);
                                }
                                break;
                            }
                        }
                    }
                }
            }

            // 转换为最终数组
            const variants = [];
            for (let [propPath, value] of combinationMap.entries()) {
                variants.push({
                    property: value.property,
                    price: value.price,
                    img: value.img
                });
            }

            // 原有逻辑：收集所有item图片（可能与变体无关）
            root.skuGalleries.item.forEach(i => {
                imgs.push(i.src);
            });

            let resultText = '';
            const firstContainer = doc.querySelectorAll('._6TwhQT0MIk')[1];
            if (firstContainer) {
                const tb = firstContainer.querySelectorAll('.a59GJHii5o');
                for (let i = 0; i < tb.length; i++) {
                    const labels = tb[i].querySelectorAll('.XsXZ-mpMmI');
                    const values = tb[i].querySelectorAll('.XZg6Q1SzDD');
                    const minCount = Math.min(labels.length, values.length);
                    for (let i = 0; i < minCount; i++) {
                        const label = labels[i].textContent.trim();
                        const value = values[i].textContent.trim();
                        resultText += `${label}：${value}\n`;
                    }
                }
            }
            const uniqueImgs = [...new Set(imgs.map(url => {
                const filename = url.split('/').pop();
                const idx = filename.lastIndexOf('_');
                return idx === -1 ? url : url.substring(0, url.length - filename.length + idx);
            }))]
            var model = {
                name: productInfo.title,
                content: productInfo.desc.content,
                imgs: uniqueImgs,
                variants,
                description: resultText
            };
            sendResponse({ model });
        }
        else if (request.Type === "GetMadeInChina") {
            const regex = /<script[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
            var productInfo = null;
            let match;
            while ((match = regex.exec(request.HtmlStr)) !== null) {
                const jsonString = match[1].trim();
                if (jsonString.includes('"image"')) {
                    const jsonObject = JSON.parse(jsonString);
                    productInfo = jsonObject;
                }
            }
            var description = "";
            for (var i = 0; i < productInfo.additionalProperty.length; i++) {
                description += productInfo.additionalProperty[i].name + "：" + productInfo.additionalProperty[i].value + "\n";
            }
            let content = $(request.HtmlStr).find('.sr-layout-main').html();

            const parser = new DOMParser();
            const doc = parser.parseFromString(content, 'text/html');

            // 2. 将文档的 body 部分转换为 jQuery 对象
            const $body = $(doc.body);

            // 3. 查找所有带有 data-original 属性的 img 标签并进行处理
            $body.find('img[data-original]').each(function () {
                const $img = $(this);
                const originalSrc = $img.attr('data-original');

                // 将 data-original 的值设置给 src
                $img.attr('src', originalSrc);

                // 移除 data-original 属性
                $img.removeAttr('data-original');
            });

            const placeholderImages = doc.querySelectorAll('img[src*="/company-profile-block-placeholder.jpg"]');
            placeholderImages.forEach(img => {
                img.remove(); // 直接移除元素
            });

            // 2. 删除具有 J-com-profile-view-more 类的按钮
            const viewMoreButtons = doc.querySelectorAll('.J-com-profile-view-more');
            viewMoreButtons.forEach(button => {
                button.remove(); // 直接移除元素
            });

            const history = doc.querySelector('.qa-form-history .J-his-qa-wp');
            if (history) {
                history.remove();
            }
            const question = doc.querySelector('.sr-layout-content .question');
            if (question) {
                question.remove();
            }
            const layout = doc.querySelector('.sr-layout-block .msg-block .J-msg-block');
            if (layout) {
                layout.remove();
            }
            const promote = doc.querySelectorAll('.sr-layout-block .msg-block .J-msg-block');
            promote.forEach(button => {
                button.remove(); // 直接移除元素
            });
            var modelContent = $body.html();
            modelContent = modelContent.replace(/<div class="sr-layout-block msg-block J-msg-block"[\s\S]*?<\/div>\s*<\/div>\s*<\/div>/g, '');
            modelContent = modelContent.replace(/<section class="sr-layout-block msg-block J-msg-block"[\s\S]*?<\/section>/g, '');
            const scriptMatch = request.HtmlStr.match(/<script[^>]*type=["']text\/data-video["'][^>]*>([\s\S]*?)<\/script>/);
            var videoUrl = '';
            if (scriptMatch && scriptMatch[1]) {
                // 2. 提取到的内容可能包含前后空白字符，先进行清理
                const jsonContent = scriptMatch[1].trim();
                const videoData = JSON.parse(jsonContent);
                videoUrl = videoData.videoUrl;
            }
            var sizeText = request.HtmlStr.match(/Package\s+Size[\s\S]*?<div\s+class="[^"]*?bac-item-value[^"]*?\s+[^"]*?fl[^"]*?"[^>]*>\s*([^<]+)/i)?.[1]?.trim();
            var sizeMatches = sizeText ? sizeText.match(/[\d.]+/g)?.map(Number) : [];
            var length = sizeMatches[0] || 0;
            var width = sizeMatches[1] || 0;
            var height = sizeMatches[2] || 0;
            var weightText = request.HtmlStr.match(/Package\s+Gross\s+Weight[\s\S]*?<div\s+class="[^"]*?bac-item-value[^"]*?\s+[^"]*?fl[^"]*?"[^>]*>\s*([^<]+)/i)?.[1]?.trim();
            var weightNumber = weightText ? weightText.match(/[\d.]+/g)?.map(Number)[0] || 0 : 0;

            if (length == 0 || width == 0 || weightNumber == 0) {
                const sizeMatch2 = request.HtmlStr.match(
                    /Package\s+Size[\s\S]*?<dd\s+class="[^"]*?bac-item-value[^"]*?fl[^"]*?"[^>]*>\s*([\d.]+\s*cm\s*\*\s*[\d.]+\s*cm\s*\*\s*[\d.]+\s*cm)/i
                );
                let sizeText2 = null;
                if (sizeMatch2 && sizeMatch2[1])
                    sizeText2 = sizeMatch2[1].trim();
                const sizeMatches2 = sizeText2 ? sizeText2.match(/[\d.]+/g)?.map(Number) : [];
                length = sizeMatches2?.[0] || 0;
                width = sizeMatches2?.[1] || 0;
                height = sizeMatches2?.[2] || 0;
                const weightMatch2 = request.HtmlStr.match(
                    /Package\s+Gross\s+Weight[\s\S]*?<dd\s+class="[^"]*?bac-item-value[^"]*?fl[^"]*?"[^>]*>\s*([\d.]+)\s*kg/i
                );
                let weightValue = 0;
                if (weightMatch2 && weightMatch2[1]) {
                    weightValue = parseFloat(weightMatch2[1]);
                }
                weightNumber = weightValue || 0;
            }
            var model = {
                name: productInfo.name,
                image: productInfo.image,
                price: productInfo.offers.price,
                description,
                content: modelContent,
                currency: productInfo.offers.priceCurrency,
                videoUrl,
                length,
                width,
                height,
                weightNumber
            };
            sendResponse({ model });
        }
        else if (request.Type === "GetPinDuoDuoHtmlData") {

            let attrArr = [];
            let iamgeSrcList = [];

            const openAttrPageButton = document.querySelector('div[role="button"].yK39frdi');
            if (!openAttrPageButton) {
                sendResponse({ data: "" });
                return;
            }

            //打开选择变体窗口
            openAttrPageButton.click();
            const container = document.querySelector('div.b482OWdu');

            const openDescPagebutton = document.querySelector('div.KvY4B91X div[role="button"]');
            //有此按钮则表示有隐藏的产品文本描述
            if (openDescPagebutton)
                openDescPagebutton.click(); //打开产品文本描述窗口

            let productName = document.querySelector('span.Vrv3bF_E')?.innerText || "";//产品名称
            let price = document.querySelector('span.kxqW0mMz')?.innerText || "";//页面价格
            let descTextArr = [];
            let descRich = "";
            let descRichImages = [];
            let videoUrl = "";

            const video = document.querySelector('video[src]');
            if (video) videoUrl = video.src;

            const descRichDiv = document.querySelector('div.UhNRiWLO');
            if (descRichDiv) {
                descRich = descRichDiv.outerHTML;
                const descImgs = descRichDiv.querySelectorAll('img');
                descImgs.forEach(img => {
                    if (img.getAttribute('data-src')) {
                        descRichImages.push(img.getAttribute('data-src'));
                    }
                });
            }

            if (container) {
                //因为图片是懒加载，并且图片有可能重复
                const imageCountLabel = document.querySelector('div.Vj7VAIVp[aria-label*="张商品图"]')?.getAttribute('aria-label') || '';
                const imageCountMatch = imageCountLabel.match(/共\s*(\d+)\s*张商品图/);
                const totalImageCount = imageCountMatch ? Number(imageCountMatch[1]) : Infinity;
                const seenImageUniqids = new Set();
                const imageSlides = container.querySelectorAll('div.QFNLpbqP div[data-uniqid]');
                let hasReachedFirstImage = false;

                imageSlides.forEach(slide => {
                    const uniqid = Number(slide.getAttribute('data-uniqid'));
                    // 轮播最前面会克隆最后一张（如 uniqid=14），因此必须从首次出现的第 1 张开始。
                    if (!hasReachedFirstImage) {
                        if (uniqid !== 1) return;
                        hasReachedFirstImage = true;
                    }

                    // 只保留第 1 到总数张的原始节点；末尾克隆节点会被 seenImageUniqids 过滤。
                    if (!Number.isInteger(uniqid) || uniqid < 1 || uniqid > totalImageCount || seenImageUniqids.has(uniqid)) return;

                    const img = slide.querySelector('img');
                    const src = img?.getAttribute('data-src') || img?.getAttribute('src');
                    if (src) {
                        seenImageUniqids.add(uniqid);
                        iamgeSrcList.push(src);
                    }
                });
            }

            const variantAttrDivs = document.querySelectorAll('div.HidQ9ROd div.i1zfKKnF div.bIhLWVqm');
            let totalAttrs = 0;
            variantAttrDivs.forEach(div => {
                const attrButtons = div.querySelectorAll('div[role="button"]');
                totalAttrs += attrButtons.length;
            });

            const container2 = document.querySelector('.i1zfKKnF');
            if (!container2) {
                console.error('没有找到父容器 .i1zfKKnF');
                return;
            }

            // 获取属性组
            const propertyGroups = Array.from(container2.querySelectorAll('.bIhLWVqm')).map(group => {
                const keySpan = group.querySelector('.sku-specs-key');
                const key = keySpan ? keySpan.textContent.trim() : '';
                const buttons = Array.from(group.querySelectorAll('div[role="button"][aria-label]'))
                    .map(btn => ({ value: btn.getAttribute('aria-label').trim(), button: btn }));
                return { key, buttons };
            });

            if (propertyGroups.length === 0) {
                console.error('没有找到任何属性组');
                return;
            }

            // 笛卡尔积
            function cartesianProduct(arrays) {
                return arrays.reduce((a, b) => a.flatMap(d => b.map(e => [...d, e])), [[]]);
            }

            const arraysForCombination = propertyGroups.map(pg =>
                pg.buttons.map(b => ({ Key: pg.key, Value: b.value, button: b.button }))
            );
            let combinations = cartesianProduct(arraysForCombination);

            combinations.sort((a, b) => {
                const aHas = a[0]?.button.classList.contains('hr353bdX') ? 0 : 1;
                const bHas = b[0]?.button.classList.contains('hr353bdX') ? 0 : 1;
                return aHas - bHas;
            });

            const result = [];
            let previousSrc = document.querySelector('div.O7pEFvHR img')?.src || "";

            // 等待图片变化函数（回调版）
            function waitForImageChange(oldSrc, callback, timeout = 1000) {
                const start = Date.now();
                const timer = setInterval(() => {
                    const imgEl = document.querySelector('div.O7pEFvHR img');
                    const priceEl = document.querySelector('div.ujEqGzEB');
                    let priceVal = "";
                    if (!imgEl) {
                        clearInterval(timer);
                        callback("", priceVal);
                        return;
                    }
                    if (imgEl.src !== oldSrc) {
                        clearInterval(timer);
                        priceVal = priceEl ? cleanPrice(priceEl.innerText) : "";
                        callback(imgEl.src, priceVal);
                        return;
                    }
                    if (Date.now() - start > timeout) {
                        clearInterval(timer);
                        priceVal = priceEl ? cleanPrice(priceEl.innerText) : "";
                        callback(imgEl.src, priceVal);
                    }
                }, 50);
            }

            // 遍历组合（用递归实现顺序点击 + 等待图片）
            function processCombo(index) {
                if (index >= combinations.length) {
                    //关闭选择变体窗口
                    const closeAttrPageButton = document.querySelector('div.O7pEFvHR div[role="button"]');
                    if (closeAttrPageButton)
                        closeAttrPageButton.click();

                    GetDescData();

                    //关闭文本描述窗口
                    const closeDescPagebutton = document.querySelector('div[role="button"][class="CRUXp2sl"]');
                    if (closeDescPagebutton)
                        closeDescPagebutton.click();

                    const model = {
                        productName,
                        iamgeSrcList,
                        attrArr,
                        variants: result,
                        price,
                        descTextArr,
                        descRich,
                        descRichImages,
                        videoUrl
                    };

                    //返回数据
                    sendResponse(model);

                    return;
                }

                const combo = combinations[index];

                // 点击每个按钮
                combo.forEach(item => {
                    if (!item.button.classList.contains('hr353bdX')) {
                        item.button.click();
                    }
                });

                // 等待图片更新后继续处理
                waitForImageChange(previousSrc, function (newSrc, newPrice) {
                    previousSrc = newSrc;

                    result.push({
                        Price: newPrice,
                        VariantImageUrl: newSrc,
                        Property: JSON.stringify(combo.map(item => ({ Key: item.Key, Value: item.Value })))
                    });

                    for (let i = 0; i < combo.length; i++) {
                        const comboElement = combo[i];
                        if (attrArr.indexOf(comboElement.Key) < 0)
                            attrArr.push(comboElement.Key);
                    }

                    // 可选短延时，防止页面过快操作
                    setTimeout(() => processCombo(index + 1), 300);
                });
            }

            // 开始处理第一个组合
            processCombo(0);


            //获取文本描述
            function GetDescData() {
                //有此按钮则表示有隐藏的产品文本描述
                if (openDescPagebutton) {
                    // 找到容器和所有目标div
                    const descContainer = document.querySelector('div.P0BQx7zD');
                    const descTargetDivs = descContainer ? descContainer.querySelectorAll('div.RY5AHn6B') : [];
                    // 循环处理每个div
                    descTargetDivs.forEach((div, index) => {
                        // 获取所有直接子div
                        const childDivs = div.querySelectorAll(':scope > div');

                        if (childDivs.length >= 2) {
                            const key = childDivs[0].textContent.trim();
                            const value = childDivs[1].textContent.trim();

                            // 创建对象并添加到公共数组
                            descTextArr.push({
                                key: key,
                                value: value
                            });
                        }
                    });

                } else {
                    const descContainer = document.querySelector('div.jvsKAdEs');
                    const descTargetDivs = descContainer ? descContainer.querySelectorAll('div.iUUH2sOQ') : [];
                    descTargetDivs.forEach((div, index) => {

                        const childDivs = div.querySelectorAll(':scope > div');

                        if (childDivs.length >= 2) {
                            const key = childDivs[0].textContent.trim();
                            const value = childDivs[1].textContent.trim();
                            // 创建对象并添加到公共数组
                            descTextArr.push({
                                key: key,
                                value: value
                            });
                        }
                    });
                }
            }

            return true;
        }
        else if (request.Type === "GetAmazonVariantData") {
            //请求产品详情页面DOM
            $.ajax({
                url: request.SouceUrl,
                method: 'GET',
                dataType: 'html',
                async: false,
                success: function (data) {
                    getAmazonVariantData(data);
                },
                error: function (jqXHR, textStatus, errorThrown) {
                }
            });

            //获取亚马逊变体数据，主要是图片和价格
            function getAmazonVariantData(pageHtml) {
                var scripts = document.querySelectorAll("script");
                if (pageHtml) {
                    let dom = new DOMParser();
                    let doc = dom.parseFromString(pageHtml, 'text/html');
                    scripts = doc.querySelectorAll("script");
                }

                var dimensionToAsinMap = {};
                for (var i = 0; i < scripts.length; i++) {
                    if (scripts[i].innerHTML.indexOf('dimensionToAsinMap') !== -1) {
                        var scriptContent = scripts[i].innerHTML;
                        var originalString = scriptContent.toString();
                        const regex = /"dimensionToAsinMap"\s*:\s*({[^}]*})/;
                        const match = originalString.match(regex);
                        if (match && match[1]) {
                            dimensionToAsinMap = JSON.parse(match[1]);
                        } else {
                            console.error('dimensionToAsinMap not found');
                            throw new Error('dimensionToAsinMap not found');
                        }

                    }
                }

                executeRequestsInBatches(dimensionToAsinMap, request)
                    .then(result => {
                        sendResponse({ variantData: result });
                    })
                    .catch(error => {
                        sendResponse({ variantData: [] });
                    });
            }
            return true;
        }
    }
}

function normalizeImageUrl(url) {
    if (!url) return '';
    // 补全协议
    if (url.startsWith('//')) url = 'https:' + url;
    if (url.startsWith('/')) url = 'https://image.doba.com' + url;
    // 替换 webp 为 jpg
    if (url.toLowerCase().endsWith('.webp')) {
        url = url.replace(/\.webp$/i, '.jpg');
    }
    return url;
}

function extractAttributesAndValues(doc) {
    const form = doc.querySelector("form.Product__Configurable");
    if (!form) {
        return null;
    }

    const attributes = [];
    const allIds = new Set();
    const propertyName = [];
    // 获取下拉框的数据
    const formGroups = form.querySelectorAll(".form-group");

    formGroups.forEach((group) => {
        const select = group.querySelector("select");

        if (select) {
            const attributeKey = select.getAttribute("id");
            const options = select.querySelectorAll("option");
            const values = Array.from(options).map((option) => {
                const valueText = option.textContent.trim();
                const match = option.value.match(/\[(.*?)\]/);
                if (match) {
                    match[1].split(", ").forEach((id) => allIds.add(Number(id)));
                }
                return valueText;
            });
            propertyName.push(attributeKey);
            attributes.push({
                key: attributeKey,
                value: values,
            });
        }
    });

    return {
        propertyName: propertyName,
        attributes: attributes,
        uniqueIds: Array.from(allIds),
    };
}
var Crawl = {
    categoryCrawlTotalNum: 0, //分类采集的产品总数
    categoryCrawlCountNum: 0, //分类采集已经采集的数量
    categoryDataList: [], //分类采集需要采集的产品数据集合
    CarwlDetailSuccessNum: 0,// 详情采集成功数量
    CarwlDetailExcuteNum: 0,//当前进度数量
    CarwlDetailErrorNum: 0,//详情采集失败数量
    CarwlDetailErrorUrl: [], //详情采集失败url
    repeatDataList: [],//重复采集数据
}

function getShopeeHtmlUrl(url) {
    var siteUrl = url,
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

function getshopeeSiteImage(id) {
    var site = "";
    if (window.location.host.indexOf("xiapibuy") !== -1) {
        site = window.location.host.split(".")[0];
    } else {
        site = window.location.host.split(".").pop();
    }
    let url = "";
    if (site === "sg" || site === "ph" || site === "vn" || site === "cl" || site === "es") {
        url = `https://cf.shopee.${site}/file/${id}`;
    } else if (site === "tw" || site === 'xiapi') {
        url = `https://s-cf-tw.shopeesz.com/file/${id}`;
    } else if (site === "id" || site === "th") {
        url = `https://cf.shopee.co.${site}/file/${id}`;
    } else if (site === "my" || site === "br" || site === "mx" || site === "ar" || site === "co") {
        url = `https://cf.shopee.com.${site}/file/${id}`;
    }
    return url;
}

function findWidgetId(obj, widgetId, keyValue) {
    for (var key in obj) {
        if (key === widgetId && obj[key].indexOf(keyValue) > -1) {
            return obj;
        } else if (typeof obj[key] === 'object') {
            var result = findWidgetId(obj[key], widgetId, keyValue);
            if (result) {
                return result;
            }
        }
    }
    return null;
}

//找货源功能获取主图方法
function GetPlatformImageUrl(platformId, platformName) {
    let getImage = new Promise((resolve, reject) => {
        var imageUrl = "";
        if (platformId == 1) {
            var imgArr = Array.from($('div[data-box-name="showoffer.gallery"] button[tabindex] img').map(function () {
                return $(this).attr('src')
            }));
            //这里使用for循环，forEach只有抛异常才能中断循环
            for (var i = 0; i < imgArr.length; i++) {
                var element = imgArr[i];
                if (imageUrl != "")
                    resolve(imageUrl);
                else
                    reject();
            }
            reject();
        } else if (platformId == 2) { 
            var images = [];
            if ($("img.ProductImageContainer__StripImage-sc-1gow8tc-7")) { 
                images = $("img[class^='ProductImageContainer__StripImage-sc-1gow8tc']").map(function () {
                    return $(this).attr('src')
                });
            }
            if (images.length > 0) {
                var image = images[0].replace("-small", "-original").replace("-large", "-original").replace("-tiny", "-original").split('?')[0];
                resolve(image);
            } else {
                throw new Error("未能成功获取产品主图，请重试！");
            }
            // receiveMessages({ "Type": "Get" + platformName + "Text" }, null, function (content) {
            //     if (content != "none") {
            //         var images = [];
            //         if (content != "none" && content.Images != null && content.Images != undefined && content.Images.length > 0) {
            //             Array.from(content.Images).forEach(function (image) {
            //                 images.push(image.replace("-small", "-original").replace("-large", "-original").replace("-tiny", "-original").split('?')[0]);
            //             });
            //         } else if (content != "none" && content.Data) {
            //             var productInfo = JSON.parse(content.Data);
            //             images.push(productInfo.productPagePicture.split('?')[0].replace("-large", "-original"));//主图
            //             if (productInfo.hasOwnProperty("extraPhotoUrls") && productInfo["extraPhotoUrls"] != null && productInfo["extraPhotoUrls"] != undefined) {
            //                 Object.keys(productInfo.extraPhotoUrls).forEach(function (key) {
            //                     images.push(productInfo.extraPhotoUrls[key].replace("-small", "-original"));
            //                 });
            //             }
            //         }

            //         if (images.length > 0) {
            //             resolve(images[0]);
            //         }
            //         else {
            //             reject();
            //         }
            //     }
            //     else {
            //         reject();
            //     }
            // });
        } else if (platformId == 3) {

            meta = document.querySelector('meta[property="og:image"]');
            if (meta && meta.content) {
                imageUrl = meta.content;
                resolve(imageUrl);
            } else {
                var jsonStr = "none";
                var scripts = document.querySelectorAll("body > script");

                for (var i = 0; i < scripts.length; i++) {
                    if (scripts[i].innerHTML.indexOf('window.runParams') != -1)
                        jsonStr = scripts[i].innerHTML.split("window.runParams")[1];
                    if (jsonStr != "none")
                        i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
                }

                if (jsonStr == "none") {
                    scripts = document.querySelectorAll("head > script");
                    for (var i = 0; i < scripts.length; i++) {
                        if (scripts[i].innerHTML.indexOf('window._dida_config_._init_data_') != -1)
                            jsonStr = scripts[i].innerHTML.split("window._dida_config_._init_data_")[1];
                        if (jsonStr != "none")
                            i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
                    }
                }

                if (jsonStr == "none") {
                    throw new Error("未能成功获取产品主图，请重试！");
                } else {
                    let interpreter = new eval5.Interpreter(window);
                    let result = interpreter.evaluate('jsondata' + jsonStr);
                    if (result && result.data) {
                        if (result.data.hasOwnProperty("imageModule") && result.data.imageModule != undefined && result.data.imageModule.imagePathList != undefined) {
                            imageUrl = result.data.imageModule.imagePathList[0];
                        } else if (result.data.hasOwnProperty("data")
                            && result.data.data.hasOwnProperty("imageView_2247")
                            && result.data.data.imageView_2247.hasOwnProperty("fields")
                            && result.data.data.imageView_2247.fields.hasOwnProperty("imagePathList")
                            && result.data.data.imageView_2247.fields.imagePathList.length > 0) {
                            resolve(result.data.data.imageView_2247.fields.imagePathList[0]);
                        } else {
                            throw new Error("未能成功获取产品主图，请重试！");
                        }
                    } else {
                        throw new Error("未能成功获取产品主图，请重试！");
                    }
                }
            }
        } else if (platformId == 4) {

            let images = [];
            var divImages = document.querySelectorAll(".imgTagWrapper")
            if (divImages.length > 0) {
                for (let img of divImages) {
                    if (img.querySelector("img")) {
                        images.push(img.querySelector("img").src);
                        break;
                    }

                }
            }
            if (images.length == 0) {
                let imageElement = document.querySelector("#imageBlock_feature_div>script");

                if (imageElement !== null) {
                    let json = imageElement.textContent;
                    let match = json.match(/var\s+data\s*=\s*({.*?});/s);

                    if (match !== null) {
                        let jsonData = match[1];
                        let jsonDataWithDoubleQuotes = jsonData.replace(/'/g, "\"")
                            .replace("\"imageBlockRenderingStartTime\": Date.now(),", "")
                            .replace(/A\.\$\.parseJSON\(\"/g, "")
                            .replace(/\"\)/g, "");

                        let jsonModel = JSON.parse(jsonDataWithDoubleQuotes);

                        if (jsonModel !== null && jsonModel.colorImages !== null && jsonModel.colorImages.initial !== null) {
                            for (let item of jsonModel.colorImages.initial) {
                                if (item.large !== null && !images.some(c => item.large.value === c)) {
                                    images.push(item.large);
                                }
                            }
                        }
                    }
                }
            }


            if (images.length > 0) {
                resolve(images[0]);
            } else {
                reject();
            }
        } else if (platformId == 5) {
            var images = $("#dt-tab ul li").map(function () {
                if ($(this).attr('data-imgs') != undefined) return JSON.parse($(this).attr('data-imgs')).original
            });
            if (images == null || images == undefined || images.length <= 0) {
                var jsonStr = "none";
                scripts = document.querySelectorAll("body script");
                for (var i = 0; i < scripts.length; i++) {
                    if (scripts[i].innerHTML.indexOf('window.__INIT_DATA=') != -1) {
                        jsonStr = scripts[i].innerHTML.split("window.__INIT_DATA=")[1];
                    }
                    if (jsonStr != "none")
                        i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
                }
                if (jsonStr != "none") {
                    var jsonObj = JSON.parse(jsonStr);
                    if (jsonObj != null
                        && jsonObj != undefined
                        && jsonObj.hasOwnProperty("globalData")) {
                        images = jsonObj.globalData.images.map(n => "https://cbu01.alicdn.com/" + n.imageURI);
                    }
                }
            }

            if (images != null && images != undefined && images.length > 0) {
                resolve(images[0]);
            } else {
                try {
                    if (document.getElementById('gallery').querySelector('div.od-gallery-turn-item-wrapper:not(.prepic-video) img')) {
                        const srcValue = document.getElementById('gallery').querySelector('div.od-gallery-turn-item-wrapper:not(.prepic-video) img').src;
                        resolve(srcValue);
                    } else {
                        const firstThumbSpan = document.querySelector('.od-scroller-module .od-scroller-item:first-child span.v-image-cover');
                        if (firstThumbSpan) {
                            const bgStyle = firstThumbSpan.style.backgroundImage || firstThumbSpan.getAttribute('style');
                            // 使用正则提取 URL
                            const match = bgStyle.match(/url\(["']?(.*?)["']?\)/i);
                            if (match && match[1]) {
                                let imageUrl = match[1].replace(/&quot;/g, ''); // 去掉 HTML 转义引号（如果存在）
                                // 确保是完整 URL
                                if (imageUrl.startsWith('//')) {
                                    imageUrl = 'https:' + imageUrl;
                                } else if (!imageUrl.startsWith('http')) {
                                    imageUrl = 'https:' + imageUrl;
                                }
                                resolve(imageUrl);
                            } else {
                                reject();
                            }
                        } else {
                            reject();
                        }

                    }
                } catch (e) {
                    reject();
                }
            }
        } else if (platformId == 6) { 
            var jsonStr = "none";
            var images = [];
            var scripts = document.querySelectorAll("body > lint > script, body > script");
            for (var i = 0; i < scripts.length; i++) {
                if (scripts[i].innerHTML.indexOf('window.detailData = ') != -1)
                    jsonStr = scripts[i].innerHTML.split("window.detailData = ")[1];
                if (jsonStr != "none")
                    i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
            }

            if (jsonStr != "none") {
                if (jsonStr.indexOf('window.') != -1)
                    jsonStr = jsonStr.substring(0, jsonStr.indexOf('window.'));
                jsonStr = jsonStr.replace(/;([^;]*)$/, '$1'); //去掉最后一个;  防止JSON.parse报错
                var obj = JSON.parse(jsonStr);
                if (obj.hasOwnProperty("globalData")) {
                    var productInfo = obj.globalData;

                    if (productInfo.product.hasOwnProperty("mediaItems")
                        && productInfo.product.mediaItems != null
                        && productInfo.product.mediaItems.length > 0) {
                        productInfo.product.mediaItems.forEach(function (item) {
                            if (item.hasOwnProperty("type")) {
                                if (item.type = "image"
                                    && item.hasOwnProperty("imageUrl")
                                    && item.imageUrl.hasOwnProperty("big")
                                    && !item.imageUrl.hasOwnProperty("fileName")) {
                                    images.push(item.imageUrl.big);
                                }
                            }
                        });
                    }
                }
            }

            if (images != null && images != undefined && images.length > 0) {
                resolve(images[0]);
            } else {
                reject();
            }
        } else if (platformId == 7) { 
            //主图，橱窗图
            var picture = [];
            if ($('div.scroller___gCiAJ ul.items___MT9MW img') && $('div.scroller___gCiAJ ul.items___MT9MW img').length > 0) {
                for (var i = 0; i < $('div.scroller___gCiAJ ul.items___MT9MW img').length; i++) {
                    picture.push($($('div.scroller___gCiAJ ul.items___MT9MW img')[i]).attr('src'));
                }
            } else if ($('.gallery___KYLUJ .content___OJbKT img') && $('.gallery___KYLUJ .content___OJbKT img').length > 0) {
                for (var i = 0; i < $('.gallery___KYLUJ .content___OJbKT img').length; i++) {
                    picture.push($($('.gallery___KYLUJ .content___OJbKT img')[i]).attr('src'));
                }
            } else if ($('div[class^="imageWrap_"] img[class^="image_"]') && $('div[class^="imageWrap_"] img[class^="image_"]').length > 0) {
                picture.push($('div[class^="imageWrap_"] img[class^="image_"]').attr('src')); 
            }
            if (picture.length > 0) {
                resolve(picture[0]);
            } else {
                reject();
            }
        } else if (platformId == 8) {
            receiveMessages({ "Type": "Get" + platformName + "Text" }, null, function (content) {
                if (content != "none" && content.Info && content.Info.image && content.Info.image != null) {
                    resolve(content.Info.image);
                } else {
                    reject();
                }
            });
        } else if (platformId == 9) {
            receiveMessages({
                "Type": "Get" + platformName + "Text",
                "sourceUrl": window.location.href
            }, null, function (content) {
                if (content != "none") {
                    if (content.isBathCollect) {
                        resolve(window.location.href);
                    } else {
                        var product = JSON.parse(content);
                        if (product && product.data.product_images != null && product.data.product_images.images != null) {
                            var imageId = product.data.product_images.images[0]
                            var image = getshopeeSiteImage(imageId)
                            if (image && image != "") {
                                resolve(image);
                            } else {
                                throw new Error("未能成功获取产品主图，请重试！");
                            }
                        } else {
                            throw new Error("未能成功获取产品主图，请重试！");
                        }
                    }

                } else {
                    reject();
                }
            });
        } else if (platformId == 10) {

            var jsonStr = "none";
            var scripts = document.querySelectorAll("body > script");
            // lazada
            for (var i = 0; i < scripts.length; i++) {
                if (scripts[i].innerHTML.indexOf('__moduleData__') != -1) {
                    jsonStr = scripts[i].innerHTML.split("__moduleData__ =")[1].split("};")[0];
                }

                if (jsonStr != "none")
                    i = scripts.length;//都取到值直接跳出循环，retrun中断循环会影响消息回传
            }
            var jsondata = JSON.parse(jsonStr + "}");

            if (jsondata != undefined && jsondata.data != undefined && jsondata.data.root != undefined && jsondata.data.root.fields != undefined) {
                var content = jsondata.data.root.fields;
                if (content.skuGalleries && content.skuGalleries != null) {
                    var images = [];
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
                    images = skuGalleries.map(x => {
                        if (x.poster.indexOf("https:") == -1)
                            return "https:" + x.poster;
                        else
                            return x.poster;
                    });
                    resolve(images[0]);
                } else {
                    reject();
                }
            } else {
                reject();
            }


        } else if (platformId == 11) { 
            if ($('img[class*="PicGallery--thumbnailPic--"]') && $('img[class*="PicGallery--thumbnailPic--"]').length > 0) {
                imageUrl = $('img[class*="PicGallery--thumbnailPic--"]').attr('src').split('.jpg')[0] + ".jpg";
                if (imageUrl.indexOf('http') == -1)
                    imageUrl = 'https:' + imageUrl;
                resolve(imageUrl);
            } else if ($('img[class^="thumbnailPic--QasTmWDm"]') && $('img[class^="thumbnailPic--QasTmWDm"]').length > 0) {
                imageUrl = $('img[class^="thumbnailPic--QasTmWDm"]').attr('src').split('.jpg')[0] + ".jpg";
                if (imageUrl.indexOf('http') == -1)
                    imageUrl = 'https:' + imageUrl;
                resolve(imageUrl);
            } else {
                reject();
            }
        } else if (platformId == 12) { 
            if (document.URL.indexOf('pifa.pinduoduo.com') >= 0) {
                var imageUrls = [];
                var imgs = document.getElementsByClassName("goods-img");
                //循环获取imgs中的src属性，并Push到imageUrl中
                for (var i = 0; i < imgs.length; i++) {
                    imageUrl = imgs[i].getAttribute("src");
                    imageUrls.push(imageUrl);
                }
                if (imageUrls.length > 0)
                    resolve(imageUrls[0]);
                else
                    reject();
            } else if (document.URL.indexOf('mobile.yangkeduo.com') >= 0) {
                var imageUrls = [];
                var imgs = [];
                var divList = document.getElementsByClassName("_1bq9lpD4");
                if (divList.length > 0)
                    imgs = document.getElementsByClassName("_1bq9lpD4")[0].getElementsByTagName("img");
                if (divList.length > 1) 
                    imgs = document.getElementsByClassName("_1bq9lpD4")[1].getElementsByTagName("img");
                
                //循环获取imgs中的src属性，并Push到imageUrl中
                for (var i = 0; i < imgs.length; i++) {
                    imageUrl = imgs[i].getAttribute("src");
                    imageUrls.push(imageUrl);
                } 
                if ($('div[class^="PPuOGFfM"] img[class^="txzZKbJX"]') && $('div[class^="PPuOGFfM"] img[class^="txzZKbJX"]').length > 0) {
                    imageUrls.push($('div[class^="PPuOGFfM"] img[class^="txzZKbJX"]').attr('src'));
                }
                if (imageUrls.length > 0)
                    resolve(imageUrls[0]);
                else
                    reject();
            } else {
                meta = document.querySelector('meta[property="og:image"]');
                if (meta && meta.content) {
                    imageUrl = meta.content;
                    resolve(imageUrl);
                } else {
                    reject();
                }
            }
            receiveMessages({ "Type": "Get" + platformName + "Text" }, null, function (content) {
                if (content != "none"
                    && content.store
                    && content.store.initDataObj
                    && content.store.initDataObj.goods) {
                    //图片
                    var imageUrls = [];
                    if (content.store.initDataObj.goods.viewImageData
                        && content.store.initDataObj.goods.viewImageData != null
                        && content.store.initDataObj.goods.viewImageData.length > 0)
                        imageUrls = content.store.initDataObj.goods.viewImageData;

                    if (content.store.initDataObj.goods.detailGallery
                        && content.store.initDataObj.goods.detailGallery != null
                        && content.store.initDataObj.goods.detailGallery.length > 0) {
                        content.store.initDataObj.goods.detailGallery.map(x => {
                            if (imageUrls.indexOf(x.url) < 0)
                                imageUrls.push(x.url);
                        });
                    }

                    if (imageUrls.length > 0)
                        resolve(imageUrls[0]);
                    else
                        reject();
                } else {
                    reject();
                }
            });
        } else if (platformId == 13) { 
            if ($('div[class^="ux-image"] img') && $('div[class^="ux-image"] img').length > 0) 
                imageUrl = $('div[class^="ux-image"] img').attr('src');
            if (imageUrl)
                resolve(imageUrl);
            else
                reject();
        } else if (platformId == 14) {
            var jsonStr = "none";
            var images = [];
            var rusJs = document.getElementById('__AER_DATA__');

            jsonStr = rusJs.innerHTML;
            let interpreter = new eval5.Interpreter(window);
            let result = interpreter.evaluate('jsondata = ' + jsonStr);
            if (result != null && result.widgets != null && result.widgets.length > 0) {
                findImage: for (var i = 0; i < result.widgets.length; i++) {
                    if (result.widgets[i].widgetId.indexOf('bx/PhoneInputContextWidget/') > -1) {
                        for (let children1 of result.widgets[i].children[0].children) {
                            if (children1.widgetId.indexOf('bx/SnowStoreContextWidget/') > -1) {
                                for (let children2 of children1.children) {
                                    if (children2.widgetId.indexOf('bx/SnowProductContextWidget/0.4.20') > -1
                                        && children2.props
                                        && children2.props.gallery
                                        && children2.props.gallery != null
                                        && children2.props.gallery.length > 0) {
                                        children2.props.gallery.forEach(x => {
                                            if (images.find(item => item == x.imageUrl) == undefined)
                                                images.push(x.imageUrl);
                                        });
                                        break findImage;
                                    }


                                }
                            }
                        }
                    } else {
                        var widgetObj = findWidgetId(result.widgets[i], 'widgetId', 'bx/SnowProductContextWidget');
                        if (widgetObj != null) {
                            widgetObj.props.gallery.forEach(x => {
                                if (images.find(item => item == x.imageUrl) == undefined)
                                    images.push(x.imageUrl);
                            });
                            break findImage;
                        }
                    }
                }
            }

            if (images && images.length > 0) {
                resolve(images[0]);
            } else {
                reject();
            }
        } else if (platformId == 15) {  
            if ($('img[class^="PicGallery--thumbnailPic"]') && $('img[class^="PicGallery--thumbnailPic"]').length > 0) {
                imageUrl = $('img[class^="PicGallery--thumbnailPic"]').attr('src').split('.jpg')[0] + ".jpg";
                if (imageUrl.indexOf('http') == -1)
                    imageUrl = 'https:' + imageUrl;
                resolve(imageUrl);
            } else if ($('#J_ImgBooth') && $('#J_ImgBooth').length > 0) {
                imageUrl = $('#J_ImgBooth').attr('src').split('.jpg')[0] + ".jpg";
                if (imageUrl.indexOf('http') == -1)
                    imageUrl = 'https:' + imageUrl;
                resolve(imageUrl);
            } else if ($('img[class^="thumbnailPic--QasTmWDm"]') && $('img[class^="thumbnailPic--QasTmWDm"]').length > 0) {
                imageUrl = $('img[class^="thumbnailPic--QasTmWDm"]').attr('src').split('.jpg')[0] + ".jpg";
                if (imageUrl.indexOf('http') == -1)
                    imageUrl = 'https:' + imageUrl;
                resolve(imageUrl);
            } else {
                reject();
            }
        } else if (platformId == 16) {
            receiveMessages({ "Type": "Get" + platformName + "Text" }, null, function (content) {
                if (content != "none"
                    && content.images
                    && content.images != null
                    && content.images.length > 0) {
                    //图片
                    var imageUrls = content.images.map(x => {
                        if (x.origin.indexOf("https:") != 0)
                            return "https:" + x.origin;
                        else
                            return x.origin;
                    });

                    if (imageUrls.length > 0)
                        resolve(imageUrls[0]);
                    else
                        reject();
                } else {
                    reject();
                }
            });
        } else if (platformId == 17) {
            receiveMessages({ "Type": "Get" + platformName + "Text" }, null, function (content) {
                if (content != "none" && content.mainImg != undefined && content.mainImg != null && content.mainImg.length > 0) {
                    resolve(content.mainImg[0]);
                } else {
                    reject();
                }
            });
        } else if (platformId == 18) { 
            if ($('ul[class^="lh"] img') && $('ul[class^="lh"] img').length > 0) {
                imageUrl = $('ul[class^="lh"] img').attr('src')
                    .replace('s114x114', 's720x720')
                    .replace('.png.avif', '.png') 
                    .replace('.jpg.avif', '.jpg');
                resolve(imageUrl);
            } else {
                reject();
            }
        } else if (platformId == 19) {
            let jsondata = $.parseJSON($(document).find("#__NEXT_DATA__")[0].innerText);
            if (jsondata
                && jsondata != null
                && jsondata.props
                && jsondata.props.pageProps
                && jsondata.props.pageProps.initialData
                && jsondata.props.pageProps.initialData.data
                && jsondata.props.pageProps.initialData.data.product
                && jsondata.props.pageProps.initialData.data.product.imageInfo
                && jsondata.props.pageProps.initialData.data.product.imageInfo.allImages
                && jsondata.props.pageProps.initialData.data.product.imageInfo.allImages.length > 0) {
                resolve(jsondata.props.pageProps.initialData.data.product.imageInfo.allImages[0].url);
            } else {
                reject();
            }

        } else if (platformId == 20) {
            meta = document.querySelector('meta[property="og:image"]');
            if (meta && meta.content) {
                imageUrl = meta.content;
                resolve(imageUrl);
            } else {
                reject();
            }
        } else if (platformId == 21) { 
            if ($('div[class^="_2AOclWz7"] img') && $('div[class^="_2AOclWz7"] img').length > 0) {
                imageUrl = $('div[class^="_2AOclWz7"] img').attr('src');
                resolve(imageUrl);
            } else if (document.querySelector('._2AOclWz7') && document.querySelector('._2AOclWz7').children) {
                imageUrl = document.querySelector('._2AOclWz7').children[0].firstChild.attributes.src.value
                resolve(imageUrl);
            } else {
                reject();
            }
        } else if (platformId == 23) { 
            if ($('div[class^="swiper-wrapper"] img') && $('div[class^="swiper-wrapper"] img').length > 0) {
                imageUrl = $('div[class^="swiper-wrapper"] img').attr('src').split('?')[0];
                if (imageUrl.indexOf("http") != 0) {
                    imageUrl = "https:" + imageUrl;
                }
                resolve(imageUrl);
            }
            else {
                reject();
            }
        } else if (platformId == 24) {
            if (document.querySelector('.tb-thumb-item')) {
                if (document.querySelector('.tb-thumb-item > a').children[0].attributes.big) {
                    imageUrl = document.querySelector('.tb-thumb-item > a').children[0].attributes.big.value
                } else {
                    imageUrl = document.querySelector('.tb-thumb-item > a').children[0].attributes.src.value
                }
                if (imageUrl.indexOf("http") != 0) {
                    imageUrl = "https:" + imageUrl;
                }
                resolve(imageUrl);
            } else {
                reject();
            }

        } else if (platformId == 25) { 
            if (document.querySelector('#photoSmall')) {
                if ($(document.querySelector('#photoSmall')).find("img")[0].attributes.alt) {
                    imageUrl = $(document.querySelector('#photoSmall')).find("img")[0].attributes.alt.value
                } else {
                    imageUrl = $(document.querySelector('#photoSmall')).find("img")[0].attributes.src.value
                }
                if (imageUrl.indexOf("http") != 0) {
                    imageUrl = "https:" + imageUrl;
                } 
                resolve(imageUrl);
            } else {
                reject();
            }
        } else if (platformId == 26) { 
            if (document.querySelector('.bimg-inner')) {
                const images = document.querySelectorAll('.bimg-inner');
                for (let i = 0; i < images.length; i++) {
                    const image = images[i];
                    if (image.attributes["data-imgurl"]) {
                        imageUrl = image.attributes["data-imgurl"].value;
                        break;
                    }
                }
                if (imageUrl.indexOf("http") != 0) {
                    imageUrl = "https:" + imageUrl;
                }
                resolve(imageUrl);
            } else if ($('div[class^="masterMap_smallMapWarp"] ul li span img') && $('div[class^="masterMap_smallMapWarp"] ul li span img').length > 0) {
                imageUrl = $('div[class^="masterMap_smallMapWarp"] ul li span img').attr('src');
                resolve(imageUrl);
            } else {
                reject();
            }

        } else if (platformId == 27) {
            if (document.querySelector('#image-gallery')) {
                const images = document.querySelectorAll('#image-gallery')[0].querySelectorAll("a");
                for (let i = 0; i < images.length; i++) {
                    const image = images[i];
                    if (image.attributes["href"]) {
                        imageUrl = image.attributes["href"].value;
                        break;
                    }
                }
                if (imageUrl.indexOf("http") != 0) {
                    imageUrl = "https:" + imageUrl;
                }
                resolve(imageUrl);
            } else {
                reject();
            }
        } else if (platformId == 22) {
            if (document.querySelector('.ui-pdp-gallery__column')) {
                const galleryColumns = document.querySelector('.ui-pdp-gallery__column');

                const wrapper = galleryColumns.querySelector('.ui-pdp-gallery__wrapper');
                if (wrapper) {
                    const figure = wrapper.querySelector('figure');
                    if (figure) {
                        const img = figure.querySelector('img');
                        if (img) {
                            imageUrl = img.getAttribute('src');
                        }
                    }
                }
                resolve(imageUrl);
            } else {
                reject();
            }
        } else if (platformId == 28) {
            if (document.querySelector('.small-img-item')) {
                const imagesli = document.querySelectorAll('.small-img-item');
                for (let i = 0; i < imagesli.length; i++) {
                    const image = imagesli[i].querySelector('a');
                    if (image && image.attributes["href"]) {
                        imageUrl = image.attributes["href"].value;
                        break;
                    }
                    const imageLable = imagesli[i].querySelector('img');
                    if (imageLable && imageLable.attributes['data-url']) {
                        imageUrl = imageLable.attributes["data-url"].value;
                        break;
                    }

                }
                if (imageUrl.indexOf("http") != 0) {
                    imageUrl = "https:" + imageUrl;
                }
                resolve(imageUrl);
            } else {
                reject();
            }

        } else if (platformId == 29) { 
            if ($('p[class^="wsy-image"] img') && $('p[class^="wsy-image"] img').length > 0) {
                imageUrl = $('p[class^="wsy-image"] img').attr('src');
                imageUrl = imageUrl.replace('.jpg_60x60.jpg', '.jpg');
                resolve(imageUrl);
            }
            else
                reject();
        } else if (platformId == 30) {
            var picElement = document.querySelector(".image-carousel-container");
            if (picElement) {
                imageUrl = picElement.querySelectorAll("li")[0].querySelector("img").getAttribute("src")
                resolve(imageUrl);
            } else {
                reject();
            }
        } else if (platformId == 35) { 
            var imgElement = document.querySelector(".j-zoom-image");
            if (imgElement) {
                var imgArr = Array.from($('.j-zoom-image').map(function () {
                    return $(this).attr('src')
                }));
                resolve(imgArr[0].replace("/c246x328/", "/big/").replace(".webp", ".jpg"));
            } else if ($('div[class^="swiper-slide"] img') && $('div[class^="swiper-slide"] img').length > 0) {
                imageUrl = $('div[class^="swiper-slide"] img').attr('src');
                resolve(imageUrl.replace("/c246x328/", "/big/"));
            } else {
                reject();
            }
        } else if (platformId == 32) {
            var tiktokImgElement = document.querySelector(".slick-slide.slick-active.slick-current");
            if (tiktokImgElement) {
                let tiktokImgUrl = tiktokImgElement.querySelector('img').getAttribute("src");
                resolve(tiktokImgUrl);
            } else {
                reject();
            }
        } else if (platformId == 36) {
            let gigab2bImgElement = document.querySelector("#image-show .el-image img");
            if (gigab2bImgElement) {
                let gigab2bImgUrl = gigab2bImgElement.getAttribute("src");
                resolve(gigab2bImgUrl);
            } else {
                reject();
            }
        } else if (platformId == 39) {
            let scripts = document.querySelectorAll('script');
            let matchingScripts = Array.from(scripts).filter(script => script.textContent.includes('window.skuInfo'));
            if (matchingScripts.length > 0) {
                let scriptContent = matchingScripts[0].textContent;
                let jsonMatch = scriptContent.match(/window\.skuInfo\s*=\s*({.*?});/);

                if (jsonMatch) {
                    // 解析 JSON 对象
                    let skuInfoJson = JSON.parse(jsonMatch[1]);
                    imageList = skuInfoJson.images.urls;
                    let decodedUrl = decodeURIComponent(imageList[0]);
                    resolve(decodedUrl);
                }
            } else { reject(); }
        } else if (platformId == 38) {
            let sheinImgBoxElement = document.querySelector(".crop-image-container");
            let sheinImgElement = sheinImgBoxElement.querySelector('img');
            if (sheinImgElement) {
                let sheinImgUrl = "https:" + sheinImgElement.getAttribute("src");
                resolve(sheinImgUrl);
            } else {
                reject();
            }
        } else if (platformId == 41) {
            let images = document.querySelector('.proimg-container').querySelectorAll("img");
            if (images.length > 0) {
                resolve(images[0].getAttribute("src"));
            } else {
                reject();
            }

        } else if (platformId == 42) {
            var imgElement = document.querySelector('div[data-auto="image-gallery-nav-item"] img');
            if (imgElement) {
                var imgSrc = imgElement.src;
                resolve(imgSrc);
            } else {
                reject();
            }
        } else if (platformId == 43) {
            var imgElement = document.querySelector("#zoom img");
            if (imgElement) {
                var imgSrc = imgElement.getAttribute('src');
                resolve(imgSrc);
            } else {
                reject();
            }
        }
        else if (platformId == 44) {
            let images = document.querySelector('.swiper-slide').querySelectorAll("img");
            if (images.length > 0) {
                resolve(images[0].getAttribute("src"));
            } else {
                reject();
            }
        }
        else if (platformId == 45) {
            let images = document.querySelector('#thumblist').querySelectorAll("img")
            if (images.length > 0) {
                resolve(images[0].getAttribute("src"));
            } else {
                reject();
            }
        }
        else if (platformId == 46) {

            resolve(document.getElementById("qccImage").src);

        }
        else if (platformId == 47) {

            resolve(document.getElementById("original-image").src);

        }
        else if (platformId == 49) {

            var imagelist = [];
            // 遍历轮播图中的每个滑块
            $(".swiper-wrapper .swiper-slide").each(function (index, element) {
                // 获取背景图的 style 属性
                var style = $(element).find("div").attr("style");
                if (style) {
                    // 从 style 字符串中解析出 URL
                    var urlStartIndex = style.indexOf("url(");
                    var imageUrl = style.slice(urlStartIndex + 5, -3); // 去掉 "url(" 和末尾的 ")"
                    if (imageUrl) {
                        imagelist.push(imageUrl);
                    }
                }
            });

            resolve(imagelist[0]);
        }
        else if (platformId == 51) {

            let imageDataJson = $("#__NEXT_DATA__").text();
            let parsedData = {};
            let imageUrls = [];

            // 解析 Next.js 预加载数据
            try {
                parsedData = JSON.parse(imageDataJson);
            } catch (parseError) {
                console.warn("Failed to parse __NEXT_DATA__ JSON from Doba", parseError);
                parsedData = {};
            }

            // 尝试从 JSON 中提取第一张主图
            let mainImageUrl = "";
            try {
                const goodsImages = parsedData.productDetail?.goodsImg || [];
                mainImageUrl = goodsImages[0]?.imgUrl || goodsImages[0]?.imgBigUrl || "";
            } catch (error) {
                mainImageUrl = "";
            }

            // 备选：从页面缩略图中获取图片
            mainImageUrl =
                mainImageUrl ||
                $(".thumb-list li:eq(1) img").attr("src") ||
                $(".thumb-list li:eq(0) img").attr("src") ||
                $(".thumb-list .swiper-slide:eq(1) img").attr("src") ||
                $(".thumb-list .swiper-slide:eq(0) img").attr("src");

            resolve(mainImageUrl);

        } else if (platformId == 54) {
            var src = $(".J-picImg-zoom-in:eq(0)").attr('src');
            if (src.indexOf('https') == -1)
                src = "https:" + src;
            resolve(src);
        } else if (platformId == 55) {
            var allImages = $('.GdRcuRgq6t img');
            var firstNonGifSrc = null;
            // 遍历所有图片，找到第一个非 GIF 的图片
            for (var i = 0; i < allImages.length; i++) {
                var imgSrc = $(allImages[i]).attr('src');
                // 使用正则表达式不区分大小写地检查是否为 GIF 文件
                if (!/\.(gif|gifv)$/i.test(imgSrc)) {
                    firstNonGifSrc = imgSrc;
                    break; // 找到了，跳出循环
                }
            }
            var src = firstNonGifSrc;
            console.log(src);
            if (src.indexOf('_') != -1) {
                src = src.split('_')[0];
            }
            if (src.indexOf('https') == -1)
                src = "https:" + src;
            console.log(src);
            resolve(src);
        } else if (platformId == 59) {
            receiveMessages({ "Type": "Get" + platformName + "Text", "sourceUrl": window.location.href }, null, function (content) {
                if (content != "none" && content.Data && content.Data.productImages && content.Data.productImages.length > 0) {
                    var imageUrl = content.Data.productImages[0].url;
                    if (imageUrl) {
                        resolve("https://cdn3.arkswift.com/" + imageUrl);
                    }
                    else {
                        reject();
                    }
                } else {
                    reject();
                }
            });
        } else {
            GrowlNotification.notify({
                title: '无忧易售',
                description: "未能成功获取产品主图，请重试！",
                type: "error",
                position: 'top-right',
                closeTimeout: 3000,
                image: { visible: true, customImage: config.logoBase64 },
            });
        }
    });
    getImage.then(imageUrl => {
        findGoods(platformId, platformName, imageUrl);
    }).catch(e => {
        if ($("#51selling_findgoods").attr('disabled'))
            $("#51selling_findgoods").removeAttr("disabled");
        $("#51selling_findgoods").text('找货源');
        GrowlNotification.notify({
            title: '无忧易售',
            description: '发生错误！未能成功获取图片地址，请稍后重试！',
            type: 'error',
            position: 'top-right',
            closeTimeout: 3000,
            image: { visible: true, customImage: config.logoBase64 },
        });
    });
}

if (document.contentType === 'text/html') {
    if (window.location.href.indexOf('shopee.') !== -1 || window.location.href.indexOf('tw.shopeesz.com') !== -1 || window.location.href.indexOf('xiapibuy.com') !== -1) {
        $(document).off('DOMNodeInserted', '#main')
            .on('DOMNodeInserted', '#main', function () {
                ShowBottomMenu();
            });
    }
}
var CONFIG, OPTIONS = {}, isshowBox = true;
var crawlShow = null;
//调用方法创建悬浮窗
ShowBottomMenu();

function ShowBottomMenu() {
    if (document.getElementById('51selling_collectioncategory')) {
        return;
    }

    var hrefUrl = window.location.href;
    var platformInfo = MatchingPlatform(hrefUrl);
    var downloadHtml = '';
    var width = '450px';
    if (hrefUrl.indexOf('detail.1688.com') > 0 || hrefUrl.indexOf('detail.m.1688.com') > 0) {
        downloadHtml = '<button type="button" id="wyysDownLoadVideo" style="font-size:13px;background-color: #0037ff3d;border-color: #0037ff3d;color: #FFF;font-weight: 300;text-decoration: none;text-align: center;line-height: 30px;height: 30px;padding: 0 20px;display: inline-block;appearance: none;cursor: pointer;border: none;border-radius:30px;margin-left: 5px;" >下载视频</button>';
        width = '540px';
    }
    if (platformInfo.PlatformId > 0) {
        if (platformInfo.PlatformId == 47) {
            if (hrefUrl.indexOf('/all') != -1)
                return;
        }

        checkVersion(function (versionInfo) {
            let updateVersionHtml = '';
            if (versionInfo && versionInfo.NeedUpdate)
                updateVersionHtml = '<a style="font-size:12px; color: #1890ff; display: inline-block; line-height: 16px;" href="https://www.51selling.com/HelpDocument/Details/8" target="_blank">检测到新版本，前往更新</a>';

            if (platformInfo.CrawlType == "detail") {
                if (platformInfo.PlatformId == 9) {
                    if (hrefUrl.indexOf('product/') == -1 && hrefUrl.indexOf('-i.') == -1) {
                        isshowBox = false
                        if (crawlShow != null) {
                            crawlShow.close();
                            crawlShow = null;
                        }
                        return;
                    } else {
                        isshowBox = true
                    }
                }
                if (platformInfo.PlatformId === 21) {
                    if (/-g-[0-9]*\.html/.test(hrefUrl) || hrefUrl.indexOf('goods.html') !== -1 || hrefUrl.indexOf('psurl.html') !== -1 || hrefUrl.indexOf('goods_id') !== -1) {
                        isshowBox = true
                    } else {
                        isshowBox = false
                    }
                }
                if (platformInfo.PlatformId == 29 || platformInfo.PlatformId == 30 || platformInfo.PlatformId == 27) {
                    isshowBox = platformInfo.isDetail
                }

                if (isshowBox && (crawlShow == null || !document.getElementById('51selling_collectiongoods'))) {
                    //抖音平台css冲突
                    if (platformInfo.PlatformId == 49) {
                        var description = `
                    <div style="display: flex;align-items: center; white-space: nowrap;gap: 12px;line-height: 1;height: 30px;padding: 0 4px;">
                        <img src="${config.logoBase64}" style="height:30px;width:auto;margin-right:4px;" /> <!-- 假设这里插入图片 -->
                        <span style="font-size:13px;">此产品支持采集到无忧易售</span>
                        <button type="button" style="flex-shrink:0; font-size:13px; background:#1B9AF7; color:#FFF; height:30px; padding:0 12px; border-radius:30px; border:none;" id="51selling_collectiongoods">开始采集</button>
                        <button type="button" style="flex-shrink:0; font-size:13px; background:#FFA500; color:#FFF; height:30px; padding:0 12px; border-radius:30px; border:none;" id="51selling_findgoods">找货源</button>
                    </div>
                    ${downloadHtml}`;
                        crawlShow = GrowlNotification.notify({
                            description: description,
                            position: 'bottom-left',
                            closeWith: "button",
                            width: width,
                        });

                    } else {
                        crawlShow = GrowlNotification.notify({
                            description: `<div style="display: flex; flex-direction: column; gap: 3px;">
                                                  <div style="display: flex; align-items: center;">
                                                    <span style="font-size:13px; margin-right:3px;">此产品支持采集到无忧易售</span>
                                                    <button type="button" style="margin-right:3px;font-size:13px; background-color: #1B9AF7;border-color: #1B9AF7;color: #FFF;font-weight: 300;text-decoration: none;text-align: center;line-height: 30px;height: 30px;padding: 0 20px;display: inline-block;appearance: none;cursor: pointer;border: none;border-radius:30px;" id="51selling_collectiongoods">开始采集</button>
                                                    <button type="button" style="font-size:13px;background-color: #FFA500;border-color: #FFA500;color: #FFF;font-weight: 300;text-decoration: none;text-align: center;line-height: 30px;height: 30px;padding: 0 20px;display: inline-block;appearance: none;cursor: pointer;border: none;border-radius:30px;" id="51selling_findgoods">找货源</button>
                                                    ${downloadHtml}
                                                  </div>
                                                  ${updateVersionHtml}
                                                </div>`,
                            position: 'bottom-left',
                            closeWith: "button",
                            image: { visible: true, customImage: config.logoBase64 },
                            width: width,
                            type: "info"
                        });
                    }
                }
            } else {
                GrowlNotification.notify({
                    description: `<div style="display: flex; flex-direction: column; gap: 3px;">
                                          <div style="display: flex; align-items: center;">
                                            <span style="font-size:13px; margin-right:3px;">此分类支持采集到无忧易售</span>
                                            <button platformid="${platformInfo.PlatformId}" platformname="${platformInfo.PlatformName}" type="button" style="margin-right:3px;font-size:13px; background-color: #1B9AF7;border-color: #1B9AF7;color: #FFF;font-weight: 300;text-decoration: none;text-align: center;line-height: 30px;height: 30px;padding: 0 20px;display: inline-block;appearance: none;cursor: pointer;border: none;border-radius:30px;" id="51selling_collectioncategory">开始采集</button>
                                          </div>
                                          ${updateVersionHtml}
                                        </div>`,
                    position: 'bottom-left',
                    closeWith: "button",
                    image: { visible: true, customImage: config.logoBase64 },
                    width: '400px',
                    type: "info"
                });
            }
        });

    }
}

//版本检查
function checkVersion(fun) {
    sendMessageToBackgroudScript({
        "Type": "GetVersion"
    }, function (response) {
        fun(response);
    });
}

if (document.contentType === 'text/html') {
    chrome.storage.sync.get({}, function (data) {
        OPTIONS = data;
        preload();
    });
}

function preload() {
    //匹配平台
    var linkrule = getLinkRule(location.href);
    try {
        CONFIG = linkrule;
        handleLinks(CONFIG.detail);
        $(window).scroll(debounceHandleLinks);
    } catch (e) {
        return;
    }
}

var debounceHandleLinks = debounce(function () {
    if (CONFIG && CONFIG.detail) {
        handleLinks(CONFIG.detail);
    }
}, 500);

//过滤超链接，将满足条件的图片上加上采集按钮
//fnBody 过滤方法的方法体
function handleLinks(fnBody) {
    //嵌套方法处理单个链接
    function handleLink(index, a) {
        if (a.dataset.wyysStatus === 'ready') return;
        var href = getCollectLinkUrl($(a), a.href);
        //如果是相对地址，浏览器会自动变成完整地址。
        //getAttribute获取的是原始地址
        if (!href && location.href.indexOf("aliexpress.") !== -1 && $(a).attr('data-href') !== undefined)
            href = 'https:' + $(a).attr('data-href');
        if (!href) return;
        if (a.getAttribute('href') === '#' || a.getAttribute('href') === '#none') return;
        if (href.indexOf('javascript:') === 0) return;
        // if (href.indexOf('//') === 0) href = location.protocol + href;
        if (href.indexOf('/') === 0) href = location.protocol + href;
        if (href.indexOf('item-img') !== -1) return;
        if (href.indexOf('bid=') !== -1 && href.indexOf("/product") == -1) return;

        try {
            //将链接与后台返回的规则进行匹配
            var test = fnBody(href);
            var localHref = window.location.href;
            if ((localHref.indexOf('joom.com') !== -1 || localHref.indexOf('temu.com') !== -1 || localHref.indexOf('alibaba.com') !== -1 || localHref.indexOf('tmall.com') !== -1) && test) {
                var $a = $(a);
                insertFetchBtn($a, href, '', localHref);
                a.dataset.wyysStatus = 'ready';
            }
            else if (test && localHref.indexOf('walmart.com') !== -1) {
                var $a = $(a);
                if ($a.parent().attr("data-item-id")) {
                    insertFetchBtn($a, href, '', localHref);
                    a.dataset.wyysStatus = 'ready';
                }
            } else if (test && localHref.indexOf('walmart.ca') !== -1) {
                var $a = $(a);
                if ($a.parent().attr("data-item-id")) {
                    insertFetchBtn($a, href, '', localHref);
                    a.dataset.wyysStatus = 'ready';
                }
            } else if (test && localHref.indexOf("shopee.")) {
                if (href.indexOf('help.tw.shopeesz.com') !== -1 || href.indexOf('seller.tw.shopeesz.com') !== -1 || href.indexOf("seller.shopee.com") !== -1) return;
                var $a = $(a);
                insertFetchBtn($a, href, '', localHref);
                a.dataset.wyysStatus = 'ready';
            } else if (test && (validArea(a) || (href.indexOf("banggood.com") !== -1 && href.indexOf("pid=") === -1))) {
                var $a = $(a);
                insertFetchBtn($a, href, '', localHref);
                a.dataset.wyysStatus = 'ready';
            }

        } catch (e) {
            //console.log(e);
        }
    }

    //速卖通需要处理href属性隐藏且列表异步加载的特殊情况
    if (location.href.indexOf("aliexpress.") !== -1)
        $.each(document.querySelectorAll('a:not([href])'), handleLink);
    if (location.href.indexOf("1688.com") !== -1)
        $.each(document.querySelectorAll('img[data-url]'), handleLink);
    else
        $.each(document.links, handleLink); //遍历页面所有的链接,如果满足条件，则加上导入按钮

}

/*
 根据a自动插入采集按钮
 $a 超链接元素
 url 超链接地址
 */

function setUrl(href) {

}

function insertFetchBtn($a, url, status, localHref) {
    var $body = $('body'), $crawl;
    $a.addClass('wyys-link'); //头部悬浮01
    //$a.parent().addClass('wyys-link-box');
    $crawl = $('<span class="wyys-link-next" data-url=""><span class="wyys-link-con-box wyysLinkConBox"><span class="wyys-link-con wyysLinkCon">采到无忧</span></span></span>').insertAfter($body);

    var fadeOutTimer = null;
    var mouseenterFn = function (event) {
        if (fadeOutTimer) {
            clearTimeout(fadeOutTimer);
            fadeOutTimer = null;
        }

        var $firstImg = /*$a.find('img:first-child') */getCrawlANode($a),
            href = '',
            crawlTop, crawlLeft, firstImgTop, firstImgLeft,
            pos, top, left;
        // 特别处理 doba.com：从 $a 向上查找最近，再找当前图片
        if (localHref.indexOf('doba.com') !== -1) {
             var $productContainer = $a.closest(
                '.selected-item-box, ' +          
                '.product-item, ' +               
                '.goods-item, ' +                 
                '.item, ' +                       
                '.product, ' +                    
                '.goods, ' +                      
                '[class*="product"], ' +          
                '[class*="goods"]'                
            );
            // 在该商品容器内查找当前轮播图的图片
            $firstImg = $productContainer.find('.slick-slide.slick-current .carousel-img').first();
            // 如果没找到图片（如加载中），回退到 $a 自身
            if ($firstImg.length === 0) {
                $firstImg = $a;
            }
            href = url;
        }
        // 其他网站使用原有逻辑
        else {
            if (status === 'hy') $firstImg = $a;
            href = getCollectLinkUrl($a, url);
        }
        if (localHref.indexOf('walmart.ca') != -1 || localHref.indexOf('walmart.com') != -1 || localHref.indexOf('temu.com') != -1 || localHref.indexOf('yiwugo.com') != -1 || localHref.indexOf('vvic.com') != -1 || localHref.indexOf('wsy.com') != -1 || localHref.indexOf('onbuy.com') != -1 || localHref.indexOf('arkswift.com') != -1 || localHref.indexOf('ebay.') != -1) {
            href = CONFIG.setUrl(href)
        }
        if ((href.indexOf("/gp/") != -1 || href.indexOf("/dp/") != -1) && href.indexOf("www.amazon.") == -1 && localHref.indexOf("www.amazon.") != -1) {
            var siteUrl = localHref.substring(localHref.indexOf("https://") + 8);
            siteUrl = "https://" + siteUrl.substring(0, siteUrl.indexOf("/") + 1);
            href = siteUrl.substring(0, siteUrl.length - 1) + href;
        }
        if (location.href.indexOf("shopee.") !== -1 && href.indexOf("shopee.") === -1) {
            href = 'https://' + location.host + href;
        } else if (location.href.indexOf("tw.shopeesz.com") !== -1 && href.indexOf("tw.shopeesz.com") === -1) {
            href = 'https://tw.shopeesz.com' + href;
        } else if (location.href.indexOf("xiapibuy.com") !== -1 && href.indexOf("xiapibuy.com") === -1) {
            href = 'https://' + location.host + href;
        } else if (!href && location.href.indexOf("aliexpress.") !== -1 && $a.attr('data-href') !== undefined) {
            href = 'https:' + $a.attr('data-href');
        } else if (location.href.indexOf("pifa.pinduoduo.com") !== -1) {
            href = 'https://pifa.pinduoduo.com' + href;
        } else if (location.href.indexOf("fruugo.") !== -1 || location.href.indexOf("fruugoaustralia.") !== -1) {
            href = location.origin + href;
        } else if (location.href.indexOf("saleyee.") !== -1) {
            href = location.origin + href;
        }
        else if (location.href.indexOf("91jf.") !== -1) {
            href = "https://detail.91jf.com" + href;
        }

        crawlTop = $crawl.offset().top;
        crawlLeft = $crawl.offset().left;
        if ($firstImg.length > 0) {
            firstImgTop = $firstImg.offset().top;
            firstImgLeft = $firstImg.offset().left;
            if ($firstImg.width() > 50)
                firstImgLeft += 20;
        } else {
            firstImgTop = $a.offset().top;
            firstImgLeft = $a.offset().left;
            if ($a.width() > 50)
                firstImgLeft += 20;
        }
        firstImgLeft ? left = firstImgLeft : left = crawlLeft;
        firstImgTop ? top = firstImgTop - 21 : top = crawlTop - 21;
        if (window.location.host.indexOf('temu.com') != -1 || window.location.host.indexOf('alibaba.com') != -1) {
            top = $a.offset().top;
        }
        if ($crawl.attr('data-url') !== href) {
            $crawl.removeClass('success').attr({ 'data-url': href }).find('.wyysLinkCon').text('采到无忧');
        }

        $crawl.css({
            'top': top,
            'left': left,
            'opacity': 1,
            'transition': 'opacity 0.1s',
            '-moz-transition': 'opacity 0.1s',
            '-webkit-transition': 'opacity 0.1s',
            '-o-transition': 'opacity 0.1s',
            'pointer-events': 'auto'
        });
    };

    var mouseleaveFn = function (event) {
        if (fadeOutTimer) {
            clearTimeout(fadeOutTimer);
        }

        fadeOutTimer = setTimeout(function () {
            $crawl.css({
                'opacity': 0,
                'transition': 'opacity .1s',
                '-moz-transition': 'opacity .1s',
                '-webkit-transition': 'opacity .1s',
                '-o-transition': 'opacity .1s',
                'pointer-events': 'none'
            });
            fadeOutTimer = null;
        }, 500);
    };

    if (localHref.indexOf('temu.com') !== -1) {
        $a.closest('.goods-container').on('mouseenter', function () {
            mouseenterFn();
        });
        $a.closest('.goods-container').on('mouseleave', function () {
            mouseleaveFn();
        });
    }

    var $eventNode = $a;

    // 1688 新版首页
    if (
        location.hostname.indexOf("1688.com") > -1 &&
        $a.is("img[data-url]")
    ) {
        $eventNode = $a.parent();
    }

    $eventNode.on("mouseenter", function () {
        mouseenterFn();
    });

    $eventNode.on("mouseleave", function () {
        mouseleaveFn();
    });

    // $a.on('mouseenter', function () {
    //     mouseenterFn();
    // });
    // $a.on('mouseleave', function () {
    //     mouseleaveFn();
    // });

    //列表页的单个产品图片上的采集按钮
    $crawl.click(function () {
        if ($('.wyys-notify').length > 0) $('.wyys-notify').remove();
        var $span = $(this);

        var fastCrawl = function () {
            if ($('[data-action="shopeebatch"]').length) $('[data-action="shopeebatch"]').removeAttr('data-action');

            sendMessageToBackgroudScript({
                "Type": "CollectionGoods",
                "IsVerifyDuplicate": true,
                "link": url
            }, function (response) {
                setTimeout(() => {
                    $span.find('.wyysLinkConBox .wyysLinkCon').text('采到无忧');
                }, 2000)
            });
        }

        if (!$span.hasClass('success')) {
            if (url.indexOf('haiyingshuju.com') == -1 && url.indexOf("detail.tmall.com") == -1)
                url = $span.attr('data-url');

            if (url.indexOf('http') == -1) {
                if (window.location.host == "www.gigab2b.com" || window.location.host.indexOf("shein.") !== -1) {
                    url = window.location.origin + "/" + url
                } else if (window.location.host == "www.wish.com" || window.location.host == "www.joom.com" || window.location.host == "www.joom.ru" || window.location.host == "www.go2.cn") {
                    url = window.location.origin + url
                } else if (window.location.host.indexOf("yandex.ru") > -1) {
                    url = window.location.origin + url
                } else if (window.location.host.indexOf("amazon.com") > -1 && url.indexOf("/sspa/") > -1) {
                    url = window.location.origin + url
                } else {
                    url = "https:" + url
                }
            }
            $span.find('.wyysLinkConBox .wyysLinkCon').text('采集中...');
            if ((url.indexOf('shopee.') !== -1 || url.indexOf('xiapibuy.') !== -1) && !$('[data-action="shopeebatch"]').length) {
                $span.attr('data-action', 'shopeebatch');
                if ($('#shopeeIframeBox').length) {
                    $('#shopeeIframeBox').attr('src', url);
                } else {
                    $('<iframe id="shopeeIframeBox" src="' + url + '"' +
                        ' style="width: 100%; height: 300px;" scrolling="auto" frameborder="0"></iframe>').appendTo('body');
                    setTimeout(() => {
                        if (!window['_LiSellingShopeeSign_']) {
                            fastCrawl();
                        }
                    }, 2000)
                }
            } else {
                fastCrawl();
            }
        }
    });
}

var getCrawlANode = function ($a) {
    var $imgNode = $a.find('img').first();

    if (window.location.href.indexOf('www.chinavasion.com') > -1) {
        if ($a.children('img').length) {
            $imgNode = $a.children('img');
        } else {
            $imgNode = $a.children('span');
        }
    }
    if (window.location.href.indexOf('www.walmart.com') > -1 || window.location.href.indexOf('www.walmart.ca') > -1) {
        $imgNode = $a.parent();
    }
    if (window.location.href.indexOf('1688.com/') > -1) {
        $imgNode = $a.find('.ad-offer-img-wrapper');
        if (!$imgNode.length && $a.is('img[data-url]')) {
            $imgNode = $a;
        }
    }

    //修复一些用背景代替图片的情况
    if (!$imgNode.length && $a.find('div').prop('style') && $a.find('div').prop('style').background) $imgNode = $a.find('div');

    return $imgNode;
};

// 1688 推荐区的商品入口常用 img[data-url] 承载详情页链接，需要和普通 a[href] 一样接入采集链路。
function getCollectLinkUrl($node, fallbackUrl) {
    var href = $node.attr('href') || $node.attr('data-url') || fallbackUrl || '';
    if (href && href.indexOf('//') === 0) {
        href = location.protocol + href;
    }
    return href;
}

//当前链接是否为有效链接
function validArea(a) {
    var $a = $(a);
    return $a.find('img').length || $a.css('background-image') !== 'none' || $a.html().indexOf('background') !== -1;
}

function debounce(func, wait, immediate) {
    var timeout;
    return function () {
        var context = this, args = arguments;
        var later = function () {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        var callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}


//重定向框
function ShowRedirectSiteBox(message, messageType, site) {
    GrowlNotification.notify({
        title: '无忧易售',
        description: message,
        type: messageType,
        position: 'top-center',
        closeTimeout: 0,
        closeWith: "button",
        image: { visible: true, customImage: config.logoBase64 },
        showButtons: true,
        buttons: {
            action: {
                text: '确认',
                callback: function () {
                    window.open(site);
                }
            },
            cancel: {
                text: '取消',
                callback: function () {
                }
            }
        }
    });
}


// 关闭类目批量采集窗口并重置状态
function CloseCategoryCollectProgressModal() {
    try {
        Crawl.categoryCrawlTotalNum = 0;
        Crawl.categoryCrawlCountNum = 0;
        Crawl.CarwlDetailErrorNum = 0;
        Crawl.CarwlDetailErrorUrl = [];
        Crawl.CarwlDetailSuccessNum = 0;
        Crawl.CarwlDetailExcuteNum = 0;
        Crawl.categoryDataList = [];
        Crawl.repeatDataList = [];
        wyysModal.hide('#wyysCategoryCollectMsgModal');
    } catch (e) {
        $('#wyysCategoryCollectMsgModal').hide();
    }
}
//单个采集
$(document).off('click', '#51selling_collectiongoods').on('click', '#51selling_collectiongoods', function () {

    // const scrollPlatformArr = ["item.jd.com"];
    // if(scrollPlatformArr.some(x => window.location.href.includes(x))){
    //     try {
    //         window.scrollBy({
    //             top: 3000,
    //             left: 0,
    //             behavior: 'smooth'
    //         });
    //     } catch (e) {
    //         // 方法2：备用方案
    //         document.documentElement.scrollTop += 3000;
    //         document.body.scrollTop += 3000;
    //     }
    // }

    sendMessageToBackgroudScript({
        "Type": "CollectionGoods",
        "IsVerifyDuplicate": true,
        "link": window.location.href
    }, function (response) {
    });
});
$(document).off('click', '#checkUrl').on('click', '#checkUrl', function () {
    if (Crawl.CarwlDetailErrorUrl.length > 0) {
        $('#wyysCopyUrl').val(Crawl.CarwlDetailErrorUrl.join('\n'));
        $('#wyysCopyUrl').select();
        document.execCommand('copy');
    }
});
$(document).off('click', 'input[name="curPage"]').on('click', 'input[name="curPage"]', function () {
    if (this.checked) {
        $("input[name='sourceUrlRepeat']").each(function () {
            $(this).prop("checked", true);
        });
    } else {
        $("input[name='sourceUrlRepeat']").each(function () {
            $(this).prop("checked", false);
        });
    }
});
//跳过采集
$(document).off('click', '.repeatCrawDefaultBtn').on('click', '.repeatCrawDefaultBtn', function () {
    wyysModal.hide('#wyysCategoryCollectRepeatCrawlModal');
});
$(document).off('click', '#collected').on('click', '#collected', function () {

    let localSite = config.url.domain() + '/main#/collectbox';
    window.open(localSite, "_blank");
});
//重复采集
$(document).off('click', '#submitRepeatCrawl').on('click', '#submitRepeatCrawl', function () {
    var sourceUrls = getCheckBoxValByName("sourceUrlRepeat");
    if (!sourceUrls) {
        receiveMessages({
            "Type": "Alter",
            "Message": "请至少选择一个产品进行采集",
            "MessageType": "error"
        }, null, function (res) {
        })
        return;
    } else {
        wyysModal.hide('#wyysCategoryCollectRepeatCrawlModal');
        var data = sourceUrls.split(",");
        //重置进度条和结果显示,发起请求
        Crawl.categoryCrawlTotalNum = data.length;
        Crawl.CarwlDetailErrorNum = 0;
        Crawl.CarwlDetailErrorUrl = [];
        Crawl.CarwlDetailSuccessNum = 0;
        Crawl.CarwlDetailExcuteNum = 0;
        Crawl.repeatDataList = [];
        receiveMessages({ "Type": "SetCategoryProgress", "ProcessType": 0 }, null, function (res) {
        })
        data.forEach(function (item) {
            sendMessageToBackgroudScript({
                "Type": "CollectionRepeatGoods",
                "IsVerifyDuplicate": false,
                "link": item
            }, function (response) {
                if (response.MessageType && response.MessageType == "success") {//采集成功
                    receiveMessages({ "Type": "SetCategoryProgress", "ProcessType": 2 }, null, function (response) {
                    });

                } else {
                    receiveMessages({
                        "Type": "SetCategoryProgress",
                        "ProcessType": 3,
                        "url": item
                    }, null, function (response) {
                    });
                }
            });
        })

    }
});

function getCheckBoxValByName(name) {
    var s = "";
    $("input[name='" + name + "']:checked").each(function () {
        var v = $(this).val();
        if (v.indexOf(",") > -1) v = v.replace(/,/g, "");
        if (s != "") s = s + ",";
        s = s + v;
    });
    return s;
}

//类目批量采集
$(document).on('click', '#51selling_collectioncategory', function () {
    if (crawlShow != null) {
        crawlShow.close();
        crawlShow = null;
    }

    Crawl.categoryCrawlTotalNum = 0;
    Crawl.categoryCrawlCountNum = 0;
    Crawl.CarwlDetailErrorNum = 0;
    Crawl.CarwlDetailErrorUrl = [];
    Crawl.CarwlDetailSuccessNum = 0;
    Crawl.categoryDataList = [];
    Crawl.repeatDataList = [];
    let localSite = config.url.domain() + '/main#/collectbox';
    // 显示采集结果框
    var bodyDom = '<div class="wyys-modal-body" style="padding:0 10px;overflow:hidden;height:115px;min-height:115px;">',
        linkUrlDom = '<a class="wyys-m-left20 wyys-aLable" id="checkUrl" href="javascript:"><span class="copy-icon wyys-m-right10">' +
            '</span>复制失败链接</a><textarea id="wyysCopyUrl" style="position:relative;top:-3000px;width:100px;height:10px;"></textarea>';
    var collectionProgressModal = '<div class="wyys-modal msg-modal" style="margin-right:40px;margin-bottom:10px;" id="wyysCategoryCollectMsgModal">' +
        '<span class="wyysCount wyys-hide">0</span><span class="wyysTotalCount wyys-hide"></span>' +
        '<div class="wyys-modal-dialog">' +
        '<div class="wyys-modal-content">' +
        '<div class="wyys-modal-head">' +
        '<span class="wyys-modal-head-title">采集分类</span>' +
        '<span class="wyys-modal-head-close">&times;</span></div>' +
        bodyDom +
        '<div class="wyys-m-top10"><span class="craw-progress"><span class="craw-progress-bar progress-bar-success crawProgressBar" role="progressbar" aria-valuenow="60" aria-valuemin="0" aria-valuemax="100" style="width: 0;"></span></span><span class="craw-progress-info"><span class="completionNum">0</span>&nbsp;/&nbsp;<span class="wyysTotalNum">0</span></span></div>' +
        '<div class="wyys-m-top10 wyys-m-bottom10 wyysCategoryCrawlNumBox">采集成功：<span class="wyys-f-blue ">0</span></div>' +
        '<div class="wyys-m-top10 wyys-m-bottom10 wyysCategoryCrawlNumBox">采集失败：<span class="wyys-f-red wyysFail ">0</span>' +
        linkUrlDom +
        '</div>' +
        '</div><div class="wyys-modal-foot"><button type="button" class="wyys-btn wyys-btn-primary"><a id="collected" class="wyys-white" style="color: #fff !important;">查看已采集数据</a></button></div></div></div></div>';
    $('<div></div>').html(collectionProgressModal).appendTo('body');

    // 重复产品采集弹框
    var repeatCrawlModal = $('<div class="wyys-modal center middle repeat-crawl-pro" id="wyysCategoryCollectRepeatCrawlModal"><div class="wyys-modal-dialog"><div class="wyys-modal-content"><div class="wyys-modal-head"><span class="wyys-modal-head-title">重复采集</span><span class="wyys-modal-head-close repeatCrawDefaultBtn">&times;</span></div><div id="repeatCrawlModalContent" class="repeatCrawlModalContent wyys-modal-body wyys-p10 repeat-crawl-modal-content"><div class="repeat-crawl-warn wyys-f15" id="repeatCrawlWarn"><span class="wyys-gray-c">重复采集提示：以下产品在无忧易售已有采集记录，若需要再次采集请手动勾选。</span></div><div class="wyys-m-top10 wyys-table-modal-box"><table class="wyys-table-modal"></table></div></div><div class="wyys-modal-foot"><div class="craw-fr"><button type="button" class="wyys-btn wyys-btn-primary" id="submitRepeatCrawl">确认采集</button><button type="button" class="wyys-btn wyys-btn-default wyys-m-left10 repeatCrawDefaultBtn">跳过</button></div></div></div></div>');
    var tableThead = '<thead><tr><th class="has-ipt"><input name="curPage" id="wyys_checkbox" type="checkbox" onclick=""/></th><th class="img-box">图片</th><th class="wyys-f-left">标题</th></tr></thead>';
    var tableTbody = '<tbody id="repeatValue"><tbody>';
    var tableCon = tableThead + tableTbody;
    repeatCrawlModal.find('.wyys-table-modal').append(tableCon);
    $('<div></div>').append(repeatCrawlModal).appendTo('body');

    var platformId = Number($(this).attr("platformId"));
    var platformName = $(this).attr("platformName");
    sendMessageToBackgroudScript({
        "Type": "CollectionCategory",
        "PlatformId": platformId,
        "PlatformName": platformName
    }, function (response) {
        var $msgModal = $('#wyysCategoryCollectMsgModal');
        $msgModal.find('.wyys-f-blue').text(0);
        $msgModal.find('.completionNum').text(0);
        $msgModal.find('.wyysFail').text(0);
        $msgModal.find('.wyysCount').text();
        $msgModal.find('.wyystotalCount').text();
        wyysModal.show('#wyysCategoryCollectMsgModal');
        Crawl.CarwlDetailExcuteNum = 0;
    });
});
$('#wyysDownLoadVideo').click(function () {
    var $video = $('video'),
        videoSrc = $video.length ? $video[0].src : '';
    if (videoSrc) {
        window.open(videoSrc, '_blank');
    } else {
        notify('当前商品无视频！', 'error');
    }
});
$(document).off('click', '#51selling_findgoods').on('click', '#51selling_findgoods', function () {
    try {
        var hrefUrl = document.URL;
        var platformUrl = MatchingPlatform(hrefUrl)
        if (platformUrl == null || platformUrl.PlatformId == undefined || platformUrl.PlatformId <= 0) {
            GrowlNotification.notify({
                title: '无忧易售',
                description: '当前网址不支持货源查找，请前往商品详情页！',
                type: 'error',
                position: 'top-right',
                closeTimeout: 3000,
                image: { visible: true, customImage: config.logoBase64 },
            });
        } else {
            GetPlatformImageUrl(platformUrl.PlatformId, platformUrl.PlatformName);
        }
    } catch (e) {
        if ($("#51selling_findgoods").attr('disabled'))
            $("#51selling_findgoods").removeAttr("disabled");
        $("#51selling_findgoods").text('找货源');
        GrowlNotification.notify({
            title: '无忧易售',
            description: '发生错误！未能成功获取图片地址，请稍后重试！',
            type: 'error',
            position: 'top-right',
            closeTimeout: 3000,
            image: { visible: true, customImage: config.logoBase64 },
        });
    }
});


function findGoods(platformId, platformName, imageUrl) {
    var needUploadPlatform = [1, 2, 4, 7, 8, 10, 13, 16, 17, 19, 20, 22, 27, 37, 39, 41, 42, 23, 25, 28, 30, 46, 47, 59];
    var notImageUrls = [9, 29, 35, 18];
    if (imageUrl == null || imageUrl == undefined || imageUrl == "")
        throw new Error("");
    let erpVerifyRedirectedUrl = config.url.verifyRedirectedAlibaba();
    var pattern = /http(?:s?):\/\/[a-zA-Z0-9][-a-zA-Z0-9]{0,62}(\.[a-zA-Z0-9][-a-zA-Z0-9]{0,62})+\.?/;
    if ((needUploadPlatform.indexOf(platformId) == -1 && imageUrl.IsPicture()) || notImageUrls.indexOf(platformId) !== -1) {
        var goodsUrl = erpVerifyRedirectedUrl + "?imgAddress=" + encodeURIComponent(imageUrl);
        window.open(goodsUrl);
    } else {
        //因这个接口调用时间比较长，点击一次禁用按钮且提示处理中，回调方法后再启用按钮
        $("#51selling_findgoods").attr({ "disabled": "disabled" });
        $("#51selling_findgoods").text('处理中');
        GrowlNotification.notify({
            title: '无忧易售',
            description: '图片处理中，请稍后.....',
            type: 'info',
            position: 'top-right',
            closeTimeout: 5000,
            image: { visible: true, customImage: config.logoBase64 },
        });

        sendMessageToBackgroudScript({ "Type": "UploadImage", "ImageUrl": imageUrl }, function (response) {
            //启用按钮
            $("#51selling_findgoods").removeAttr("disabled");
            $("#51selling_findgoods").text('找货源');

            if (!response || response == '' || response == imageUrl) {
                var goodsUrl = erpVerifyRedirectedUrl + "?imgAddress=" + encodeURIComponent(response);
                ShowRedirectSiteBox("图片处理失败，请前往www.51selling.com检查登录状态，是否继续使用未经处理的图片找货源（可能导致查找失败）？", "warning", goodsUrl);
            } else {
                var goodsUrl = erpVerifyRedirectedUrl + "?imgAddress=" + encodeURIComponent(response);
                window.open(goodsUrl);
            }

        });
    }
}

var getCookie = function (name) {
    var arr = document.cookie.match(new RegExp("(^| )" + name + "=([^;]*)(;|$)"));
    if (arr != null) return unescape(arr[2]);
    return null
};

function getLinkRule(url) {
    if (!url) {
        return "Invalid url...";
    }
    var rule = "";
    if (url.indexOf('aliexpress.us') !== -1) {//速卖通美国站点使用.com规则,全局有两个地方要改，需要改这里记得全局搜索下域名
        rule = platformLinkRule['aliexpress.com'];
    } else if (url.indexOf('walmart.com.mx') !== -1) {
        rule = platformLinkRule['walmart.com.mx'];
    } else {
        $.each(platformLinkRule, function (key, value) {
            if (url.indexOf(key) !== -1) {
                rule = value;
                return false;
            }
        });
    }

    if (!rule) {
        return "The platform does not support the collection, we will deal with as soon as possible";
    }
    return rule;
}

// 增加一个名为 IsPicture 的函数作为String 构造函数的原型对象的一个方法
String.prototype.IsPicture = function () {
    //判断是否是图片 - strFilter必须是小写列举
    var strFilter = ".jpeg|.gif|.jpg|.png|.bmp|.pic|"
    if (this.indexOf(".") > -1) {
        var p = this.lastIndexOf(".");
        var strPostfix = this.substring(p, this.length) + '|';
        strPostfix = strPostfix.toLowerCase();
        if (strFilter.indexOf(strPostfix) > -1) {
            return true;
        }
    }
    return false;
}

//计算表达式的值
//function myeval(data, callback) {
//    var pwd = guid();
//    data.LiSellingTempPwd = pwd;
//    const iframe = document.getElementById('51selling_sandbox');
//    window.addEventListener('message', (event) => {
//        try {
//            var res = JSON.parse(event.data.data);
//            if (event.data.LiSellingTempPwd && event.data.LiSellingTempPwd == data.LiSellingTempPwd) {
//                callback(res);
//            }
//        } catch (e) { }

//    });

//    iframe.contentWindow.postMessage(data, "*");
//}

//生成一个GUID
function guid() {
    function S4() {
        return (((1 + Math.random()) * 0x10000) | 0).toString(16).substring(1);
    }

    return (S4() + S4() + "-" + S4() + "-" + S4() + "-" + S4() + "-" + S4() + S4() + S4());
}

//构建异步方法按顺序执行的队列
//function queue(arr) {
//    var sequeue = Promise.resolve();
//    arr.forEach(function (item) {
//        sequeue = sequeue.then(item);
//    });
//    return sequeue;
//}


$(function () {
    $(document).ready(function () {
        var num = 0;
        var timer = setInterval(function () {
            if (num > 10) {
                clearInterval(timer);
            }
            num++;

            if ($('#51selling_collectiongoods') && $("#51selling_collectiongoods").length > 0) {
                let element = $('#51selling_collectiongoods').closest('.growl-notification__body').get(0);
                let doc = element.ownerDocument;
                let { x, y, width, height } = element.getBoundingClientRect();
                x |= 0;
                y |= 0;
                width |= 0;
                height |= 0;
                let elements = [
                    doc.elementFromPoint(x, y),
                    doc.elementFromPoint(x + width, y),
                    doc.elementFromPoint(x, y + height),
                    doc.elementFromPoint(x + width, y + height)
                ];
                var eles = elements.filter((el) => el !== null && el !== element);

                for (var i = 0; i < eles.length; i++) {
                    if ($($(eles[i])[0]).attr('class') == 'mango-fetch')
                        $($(eles[i])[0]).css({ 'z-index': '2147483646' });
                }
            }
        }, 1000);

        if (location.href.indexOf("aliexpress.")) {//速卖通有异步加载的情况，持续15秒，每秒检测一次
            var aliexpressNum = 0;
            var aliexpressTimer = setInterval(function () {
                if (aliexpressNum > 15)
                    clearInterval(aliexpressTimer);
                aliexpressNum++;
                preload();
            }, 1000);
        }
    });

})


function waitForMethod(methodName, timeout = 5000) {
    return new Promise((resolve, reject) => {
        const startTime = Date.now();
        const checkInterval = setInterval(() => {
            if (typeof window[methodName] === 'function') {
                clearInterval(checkInterval);
                resolve(window[methodName]);
            } else if (Date.now() - startTime > timeout) {
                clearInterval(checkInterval);
                reject(new Error(`方法 ${methodName} 加载超时`));
            }
        }, 100);
    });
}

//递归找到coupang页面json数据中的atfData对象数据
function findAtfData(obj) {
    // 如果当前对象就是 atfData，直接返回
    if (obj && obj.hasOwnProperty('atfData')) {
        return obj.atfData;
    }

    // 遍历对象的属性
    if (typeof obj === 'object' && obj !== null) {
        for (let key in obj) {
            if (obj.hasOwnProperty(key)) {
                // 递归搜索
                const result = findAtfData(obj[key]);
                if (result !== undefined) {
                    return result;
                }
            }
        }
    }

    // 如果是数组，遍历数组元素
    if (Array.isArray(obj)) {
        for (let item of obj) {
            const result = findAtfData(item);
            if (result !== undefined) {
                return result;
            }
        }
    }

    return undefined; // 没找到
}

//只保留拼多多来源链接中的goods_id和uin参数
function extractGoodsId(url) {
    try {
        const parsedUrl = new URL(url);
        const goodsId = parsedUrl.searchParams.get("goods_id");

        if (!goodsId) {
            return { goodsId: null, newUrl: null };
        }

        const newUrl = `${parsedUrl.origin}${parsedUrl.pathname}?goods_id=${goodsId}`;
        return { goodsId, newUrl };
    } catch (error) {
        console.error("URL 解析错误:", error);
        return { goodsId: null, newUrl: null };
    }
}

//美客多替换Url参数
function updateMercadoUrlWithColor(url, base64Value, attrName) {
    const param = `${attrName}:${base64Value}`;

    // 1️⃣ 去掉 hash（# 及其后内容）
    const cleanUrl = url.split("#")[0];

    // 2️⃣ 拆分 path 和 query 参数
    const [path, queryString] = cleanUrl.split("?");
    const params = new URLSearchParams(queryString || "");

    // 3️⃣ 设置 attributes 参数（会自动编码一次）
    params.set("attributes", param);

    // 4️⃣ 拼接回新 URL
    return `${path}?${params.toString()}`;
}

//去掉字符串中的字符转为数字
function cleanPrice(str) {
    if (!str) return 0;

    // 去掉除数字和小数点外的所有字符
    const result = str.replace(/[^0-9.]/g, '');

    // 只保留第一个有效的小数结构（防止多个点）
    const clean = result.match(/^\d*\.?\d*/)?.[0] || '0';

    // 转成数字类型（无效则返回0）
    const num = parseFloat(clean);
    return isNaN(num) ? 0 : num;
}

function fetchWithCallback(url, options, callback) {
    chrome.runtime.sendMessage(
        {
            type: 'PROXY_FETCH',
            payload: { url: url, options: options || {} }
        },
        function (response) {
            // 请求完成后，直接执行你传进来的回调函数
            callback(response);
        }
    );
}

// 提取 Mercado 链接中的商品标识，用于判断广告链接、变体链接、详情页链接是否指向同一个商品。
function collectMercadoProductTokens(rawUrl) {
    const tokens = [];
    if (!rawUrl) {
        return tokens;
    }

    try {
        const url = new URL(rawUrl);
        const pushMatches = function (text) {
            if (!text) {
                return;
            }

            const matches = String(text).match(/MLM[A-Z0-9]+|ML[A-Z]{1,3}[A-Z0-9]+/g);
            if (matches) {
                matches.forEach(function (item) {
                    tokens.push(item.toUpperCase());
                });
            }
        };

        pushMatches(url.pathname);
        url.searchParams.forEach(function (value) {
            pushMatches(value);
        });
        pushMatches(url.hash);
    } catch (e) { }

    return Array.from(new Set(tokens));
}

// 判断两个 Mercado URL 是否指向同一个商品；优先比较域名和路径，路径不同则通过商品标识兜底匹配。
function isSameMercadoProductPage(requestUrl, currentUrl, doc) {
    try {
        const request = new URL(requestUrl);
        const current = new URL(currentUrl);
        if (request.origin !== current.origin) {
            return false;
        }

        if (request.pathname === current.pathname) {
            return true;
        }

        const requestTokens = collectMercadoProductTokens(requestUrl);
        const currentTokens = collectMercadoProductTokens(currentUrl);
        if (requestTokens.length > 0 && currentTokens.some(function (item) { return requestTokens.includes(item); })) {
            return true;
        }

        const canonicalLink = doc && doc.querySelector ? doc.querySelector('link[rel="canonical"]') : null;
        const canonicalUrl = canonicalLink ? canonicalLink.href : "";
        const canonicalTokens = collectMercadoProductTokens(canonicalUrl);

        if (canonicalUrl) {
            try {
                if (new URL(canonicalUrl).pathname === request.pathname) {
                    return true;
                }
            } catch (e) { }
        }

        return requestTokens.length > 0 && canonicalTokens.some(function (item) { return requestTokens.includes(item); });
    } catch (e) {
        return false;
    }
}

if (window.location.hostname.includes('www.tiktok.com')) {
    var tiktokDisplayNum = 0;
    var tiktokDisplayTimer = setInterval(function () {
        if (tiktokDisplayNum > 20) {
            clearInterval(tiktokDisplayTimer);
        }
        tiktokDisplayNum++;

        const collectBtn = document.getElementById('51selling_collectiongoods');
        if (!collectBtn) {
            ShowBottomMenu();
        } else {
            clearInterval(tiktokDisplayTimer);
        }
    }, 1000);
}
