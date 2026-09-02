var repeatData = [];
var successUrls = [];
var failUrls = [];
var failReasons = []
var urls;
var isNeedWait = false;
var supportPlatforms = [1, 2, 3, 4, 13, 14, 5, 6, 10, 11, 12, 15, 19, 20, 21, 22, 23, 24, 25, 26, 28, 29, 30, 35, 32, 36, 39, 38, 41, 42, 43, 44, 45, 47, 51, 54, 55, 59];//支持批量采集的平台

//配置版本号
$.getJSON('../manifest.json', function (data) {
    $("#label-version").text("V" + data.version);
})

//初始化暂停时间
$("#stopTime").val(window.localStorage.getItem("stopTime") ? window.localStorage.getItem("stopTime") : 0);

// 进度条
function setProgress(rate) {
    var s = (rate * 100).toFixed(2) + '%';
    var progressbar = $('#progressbar');
    progressbar.attr('data-precent', s);
    progressbar.find('div').attr('style', 'width:' + s);
}

//本地保存输入的暂停间隔
$("#stopTime").on("input", function () {
    $(this).val($(this).val().replace(/-/g, ""));
    window.localStorage.setItem('stopTime', $(this).val());
});

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

var controller;
// '开始采集'事件
$("#urlCollectBtn").click(function () {
    urls = [];
    repeatData = [];
    successUrls = [];
    failUrls = [];
    failReasons = [];
    isNeedWait = false;




    if ($('#urlCollect').val() === '') {
        errorTip('采集地址为空，请填写采集的URL地址。');
        return;
    } else addCollectResults()

    $('.div-repeat').show();
    $('.successNum').text(0);
    $('.errorNum').text(0);
    $('.repeatNum').text(0);
    $('.copyText').text('')
    $('.wyys-main-link').html('');

    removeErrorStyle()   // 移除错误提示
    $('tbody').html('') // 移除表格内容
    setProgress(0)      //清空进度条

    urls = $('#urlCollect').val().split('\n').map(x => x.trim()).filter(x => x);
    urls = Array.from(new Set(urls))//去重

    function getHtml(url, config) {
        var options = { url: url, method: 'GET', timeout: TIMEOUT, headers: { 'x-mango-tid': tabId } };
        if (config) {
            switch ((config.method || '').toLowerCase()) {
                case 'post':
                    options.method = 'POST';
                    break;
                case 'request':
                    options.method = 'POST';
                    options.headers = {
                        'Content-Type': 'application/json'
                    };
                    options.transformRequest = function (value) {
                        return angular.toJson(value);
                    };
                    break;
            }
            if (config.body) {
                options.data = config.body;
            }
        }

        return $q(function (resolve, reject) {
            var times = 0;
            request();

            function request() {
                ++times;
                //$http.get(url, {timeout:TIMEOUT}).success(function (data, statusCode) {
                $http(options).success(function (data, statusCode) {
                    if (typeof data === 'object') {
                        data = JSON.stringify(data);
                    }
                    resolve(data);
                }).error(function () {
                    if (times < MAX_TRY_TIMES) {
                        request();
                        $log.warn('[get]' + times + ':' + url);
                    } else {
                        //重试3次失败后，客户端放弃采集，服务端进行重试
                        reject(new Error('产品可能已下架，请点击产品查看'));
                        $log.error('[get]' + times + ':' + url);
                    }
                });
            }
        });
    }

    console.log('当前总数量1：' + urls.length);
    VerifyLogin(//验证是否登录
        function () {
            controller = newSyncExecute(urls, true, () => {
                // 采集重复处理
                if (repeatData.length > 0) {
                    removeCollectResults();
                    addRepeatDataTable();
                    $("#selectAll").prop("checked", false);
                    var tbody = $('tbody');
                    tbody.html('')
                    $.each(repeatData, function (index, item) {
                        var tr = $('<tr>');
                        tr.append($('<td>').append($('<input>').attr('type', 'checkbox').attr('data-id', item.CollectBoxId).addClass('select').click(select)));
                        tr.append($('<td>').append($('<img class="imgStyle">').attr('src', item.ImageUrl ? item.ImageUrl.split('|')[0] : "")));
                        tr.append($('<td>').text(item.Title));
                        /*tr.append($('<td>').text(item.CollectBoxVariants[0].Price));*/
                        tbody.append(tr);
                    });
                }
                failToCopy();
                collectionResNum();
            });
        },
        function () {
            removeCollectResults()
            ShowRedirectSiteBox('当前无登录用户，请先前往https://www.51selling.com/进行登录！', 'warning', config.url.domain() + "/User/Login")
        }
    );

});

//新同步执行采集
function newSyncExecute(collectUrls, isVerifyDuplicate, successFun) {
    let index = 0; // 用于迭代处理 URL 的索引
    const abortController = new AbortController();
    const executeNext = () => {
        if (index < collectUrls.length) {
            const url = collectUrls[index];
            BatchExecuteProductAcquisitionLogic(url, isVerifyDuplicate, abortController.signal, function (data, t2, t3) {
                if (data.CollectBoxId) {
                    if (data.SourceUrl.indexOf("market.yandex.ru")) {
                        data.SourceUrl = url;
                    }
                    repeatData.push(data);
                } else {

                    let isExecuteMercado = data.Type != "GetMercadoPageData" && data.Type != "GetMercadoVariantData" && data.Type != "GetMercadoHtml";
                    if (isExecuteMercado) {
                        isNeedWait = true;
                    }

                    if (data.MessageType && data.MessageType === "success" && isExecuteMercado) {
                        successUrls.push(url);
                    }
                    else if (data.MessageType && data.MessageType === "error" && isExecuteMercado) {
                        failUrls.push(url);
                        failReasons.push(data.Message);
                    }
                    else if (data.Type && data.Type === "GetDocumentCookies" && t3) {
                        t3(null);
                        return;
                    }
                    else if (data.Type && data.Type === "GetMercadoHtml" && t3) {
                        getMercadoHtml(data.RequestUrl, t3);
                        return;
                    }
                    else if (data.Type && data.Type === "GetAjaxResult" && t3) {
                        $.ajax({
                            type: data.RequestMethod,
                            headers: data.RequestHeaders,
                            xhrFields: {
                                withCredentials: true
                            },
                            url: data.RequestUrl,
                            async: false,
                            contentType: data.RequestContentType,
                            dataType: data.RequestDataType,
                            data: data.RequestData,
                            success: function (response) {
                                t3({ IsSuccess: true, Data: response });
                            },
                            error: function (jqXHR, textStatus, errorThrown) {
                                t3({ IsSuccess: false, Data: jqXHR });
                            }
                        });
                        return;
                    }
                    else if (data.Type && data.Type === "GetOnbuyVariationsInfo" && t3) {
                        let skuFirstImage = '';
                        let price = 0;

                        try {
                            let dom = new DOMParser();
                            let imageDoc = dom.parseFromString(data.HtmlStr, 'text/html');
                            let imagesElement = imageDoc.querySelector("#image-gallery").querySelectorAll("a");
                            skuFirstImage = imagesElement[0].attributes["href"].value;
                            let priceString = imageDoc.querySelector(".q-p").querySelector(".price").innerText;
                            price = parseFloat(priceString.replace(/[^\d.]/g, ''));
                        } catch (e) { }

                        t3({ SkuFirstImage: skuFirstImage, Price: price });
                        return;
                    }
                    else if (data.Type && data.Type === "GetOnbuyProductInfo" && t3) {
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
                            let doc = parser.parseFromString(data.HtmlStr, 'text/html');
                            title = doc.querySelectorAll(".product-name")[0].innerHTML;
                            desc = doc.querySelector("#product-description").outerHTML;
                            desc = desc.replace(/<div\s+class="desc-right"\s*>[\s\S]*?<\/div>/, '');
                            let topModel = JSON.parse(doc.querySelector(".top-info").querySelector('script').textContent)
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

                                    function helper(index1, combination) {
                                        if (index1 === properties.length) {
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

                                        const property = properties[index1];
                                        const values = property.value;

                                        for (const value of values) {
                                            const newCombination = { ...combination };
                                            newCombination[`attributeKey${index1 + 1}`] = property.key.replace(":", '');
                                            newCombination[`attributeValue${index1 + 1}`] = value.value;
                                            newCombination[`attribute${index1 + 1}Id`] = value.id;
                                            //newCombination['price'] = content.price;
                                            newCombination['imageUrl'] = '';
                                            newCombination['hasStock'] = 0;
                                            helper(index1 + 1, newCombination);
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

                        t3(
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
                        return;
                    }
                    else if (data.Type === 'GetFruugoProductInfo') {
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
                            let doc = parser.parseFromString(data.HtmlStr, "text/html");
                            const skuInfo = extractAttributesAndValues(doc);
                            const skuid = Number(
                                doc.querySelector('input[name="skuId"]').value
                            );
                            desc = doc.querySelector("#description").outerHTML;
                            const lastItemLink = doc.querySelector(
                                "ol li:last-child a.breadcrumb__link"
                            );
                            var title = doc.querySelector('.js-product-title').innerHTML;
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

                            if (price === 0) {
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
                        t3({
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
                    }
                    else if (data.Type === 'GetFruugoVariationsInfo') {
                        let imageList = [];
                        let price = 0;
                        let currency = '';
                        let skuAttr = [];
                        try {
                            let parser = new DOMParser();
                            let doc = parser.parseFromString(data.HtmlStr, "text/html");
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
                        t3(
                            {
                                Currency: currency,
                                Price: price,
                                ImageList: imageList,
                                SkuAttr: skuAttr
                            });
                        return true;
                    }
                    else if (data.Type === 'GetSaleyeeProductInfo') {
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
                            let doc = parser.parseFromString(data.HtmlStr, "text/html");
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
                            categoryUrl = lastItemLink.getAttribute("href");
                        } catch (e) { }
                        t3(
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
                    }
                    else if (data.Type === 'GetSaleyeeCategory') {
                        let categoryId = 0
                        try {
                            let parser = new DOMParser();
                            let doc = parser.parseFromString(data.HtmlStr, "text/html");
                            var scriptText = doc.querySelector(".headtopmargin").querySelector("script").innerText;
                            const cate3Match = scriptText.match(/cate3:\s*(\d+)/);
                            categoryId = cate3Match ? parseInt(cate3Match[1], 10) : null;
                        } catch (e) { }
                        t3({
                            id: categoryId
                        })

                    }
                    else if (data.Type === 'GetSaleyeeDesc') {
                        let parser = new DOMParser();
                        let doc = parser.parseFromString(data.HtmlStr, "text/html");
                        doc.querySelector(".choose_description").innerHTML = data.desc;
                        t3({
                            desc: doc.querySelector(".layui-tab-item").outerHTML
                        })
                    }
                    else if (data.Type && data.Type === 'GetJF91ProductInfo' && t3) {

                        let goodsId = "";
                        let specData = [];
                        let dataIds = [];
                        try {
                            const parser = new DOMParser();
                            const doc = parser.parseFromString(data.HtmlStr, 'text/html');

                            const specDiv = doc.querySelector('div[name="init[]"][type="specs"]');
                            const specContent = specDiv.textContent.trim();
                            specData = JSON.parse(specContent);

                            const goodsIdDiv = doc.querySelector('div[name="init[]"][type="goodsid"]');
                            const goodsIdContent = goodsIdDiv.textContent.trim();
                            goodsId = JSON.parse(goodsIdContent);

                            const specPicListDiv = doc.querySelector('div.spec_pic_list');

                            if (specPicListDiv) {
                                // 在 spec_pic_list 内找到所有 sp_div 中的 a 标签，并提取 data-id 属性
                                dataIds = Array.from(specPicListDiv.querySelectorAll('div.sp_div a[data-id]')).map(anchor => anchor.getAttribute('data-id')).filter((dataId, index, self) => self.indexOf(dataId) === index); // 去重
                            }
                        } catch (e) { }

                        t3({
                            goodsId: goodsId,
                            specs: specData,
                            dataIds
                        });

                        return true;
                    }
                    else if (data.Type === "GetTiktokData") {
                        let resData = null;
                        try {
                            const doc = new DOMParser().parseFromString(data.HtmlStr, 'text/html');
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

                        t3({
                            data: resData
                        });

                        return true;
                    }
                    else if (data.Type === "GetYandexProductInfo") {
                        let resData = {};
                        let dom = new DOMParser();
                        let doc = dom.parseFromString(data.HtmlStr, 'text/html');
                        try {
                            const content = Array.from(doc.querySelectorAll('noframes[data-apiary="patch"]'))
                                .find(tag => {
                                    const text = tag.textContent || tag.innerHTML;
                                    return text.includes("oskuId") && text.includes("businessId");
                                })
                                ?.textContent || "";

                            if (content && content != "") {
                                let contentObj = JSON.parse(content);
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

                        t3({ data: resData, variantArr });
                        return true;
                    }
                    else if (data.Type === "GetYandexData") {
                        let resData = {};
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

                        t3({ data: resData });
                        return true;

                    }
                    else if (data.Type === "GetBaoNiuNiuData") {

                        let images = [];
                        let atrbuts = [];
                        let titlename = "";

                        try {
                            let parser = new DOMParser();
                            let doc = parser.parseFromString(data.HtmlStr, "text/html");
                            doc.querySelector('#thumblist').querySelectorAll("img").forEach(item => {
                                if (item.getAttribute("big") && item.getAttribute("big").indexOf(".gif") < 0)
                                    images.push(item.getAttribute("big"));
                            });
                            doc.querySelector('#productmemo').querySelectorAll("img").forEach(item => {
                                if (item.src.indexOf(".gif") < 0)
                                    images.push(item.src);
                            });
                            doc.querySelector('#propshowbox').querySelectorAll("span").forEach(item => {
                                atrbuts.push(item.textContent);
                            });
                            titlename = doc.querySelector('.huohao').textContent;

                        } catch (e) {
                            console.log(e)
                        }
                        t3({ images: images, atrbuts: atrbuts, titlename: titlename });
                        return true;
                    }
                    else if (data.Type === "GetSheinPagePrice") {
                        let price = "0";
                        let dom = new DOMParser();
                        let doc = dom.parseFromString(data.HtmlStr, 'text/html');
                        try {
                            price = doc.getElementById("productMainPriceId").innerText;
                        } catch (e) { }

                        t3({ price });
                        return true;
                    }
                    else if (data.Type === "GetBanggoodProductLanguage") {
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
                        t3({
                            data: language
                        });

                        return true;
                    }
                    else if (data.Type === "CheckPinDuoDuoProductInfo") {

                        // 解析 HTML 字符串
                        let dom = new DOMParser();
                        let document = dom.parseFromString(data.HtmlStr, 'text/html');

                        // 获取所有 script 标签
                        const scripts = document.getElementsByTagName("script");

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
                            t3({
                                data: data.HtmlStr
                            });
                            return true;
                        }
                        const extractGood = extractGoodsId(data.SouceUrl);
                        $.ajax({
                            type: "GET",
                            url: extractGood.newUrl,
                            async: false,
                            contentType: "application/json",
                            dataType: "text",
                            success: function (html) {
                                console.log("html", html);
                                t3({
                                    data: html
                                });
                            },
                            error: function (results) {
                                t3({
                                    data: "",
                                });
                            }
                        });
                    }
                    else if (data.Type === "GetOnbuyPageHtml") {
                        $.ajax({
                            type: "GET",
                            url: data.SouceUrl,
                            async: false,
                            contentType: "application/json",
                            dataType: "text",
                            success: function (html) {
                                console.log("html", html);
                                t3(
                                    {
                                        data: html
                                    });
                            },
                            error: function (results) {
                                t3(
                                    {
                                        data: "",
                                    });
                            }
                        });
                    }
                    else if (data.Type === "GetMercadoPageData") {
                        let dom = new DOMParser();
                        let htmlDoc = dom.parseFromString(data.HtmlStr, 'text/html');
                        //console.log(data.HtmlStr);
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
                                        } else { }
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
                                        } catch (e) { }
                                    }
                                }
                            }
                        }
                        //console.log("model", JSON.stringify(model));
                        t3({ model });
                    }
                    else if (data.Type === "GetMercadoVariantData") {
                        let requestUrl = updateMercadoUrlWithColor(data.SouceUrl, data.AttrId, data.ColorName);
                        let variantImages = [];
                        $.ajax({
                            type: "GET",
                            url: requestUrl,
                            async: false,
                            contentType: "application/json",
                            dataType: "text",
                            success: function (html) {
                                try {
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
                                    if (pictruesObj)
                                        pictruesObj = model.initialState.components;

                                    let picturesList = pictruesObj.gallery.pictures;
                                    for (let i = 0; i < picturesList.length; i++) {
                                        let pic = picturesList[i];
                                        if (pic.id != null) {
                                            let picPath = imgTempConfig.replace("{id}", pic.id);
                                            variantImages.push(picPath);
                                        }
                                    }
                                    t3({ data: variantImages });

                                } catch (e) {
                                    t3({ data: variantImages });
                                }
                            },
                            error: function (results) {
                                t3({ data: variantImages });
                            }
                        });
                    }
                    else if (data.Type === "GetDoba") {
                        const parser = new DOMParser();
                        let domhtml = parser.parseFromString(data.HtmlStr, 'text/html');
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
                        t3({ model });
                    }
                    else if (data.Type === "GetPinDuoDuoSkuInfo") {
                        t3({ data: "批量采集失败" });
                    }
                    else if (data.Type === "GetMadeInChina") {
                        const regex = /<script[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script>/gi;
                        var productInfo = null;
                        let match;
                        while ((match = regex.exec(data.HtmlStr)) !== null) {
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
                        let content = $(data.HtmlStr).find('.sr-layout-main').html();

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
                        const scriptMatch = data.HtmlStr.match(/<script[^>]*type=["']text\/data-video["'][^>]*>([\s\S]*?)<\/script>/);
                        var videoUrl = '';
                        if (scriptMatch && scriptMatch[1]) {
                            // 2. 提取到的内容可能包含前后空白字符，先进行清理
                            const jsonContent = scriptMatch[1].trim();
                            const videoData = JSON.parse(jsonContent);
                            videoUrl = videoData.videoUrl;
                        }
                        var sizeText = data.HtmlStr.match(/Package\s+Size[\s\S]*?<div\s+class="[^"]*?bac-item-value[^"]*?\s+[^"]*?fl[^"]*?"[^>]*>\s*([^<]+)/i)?.[1]?.trim();
                        var sizeMatches = sizeText ? sizeText.match(/[\d.]+/g)?.map(Number) : [];
                        var length = sizeMatches[0] || 0;
                        var width = sizeMatches[1] || 0;
                        var height = sizeMatches[2] || 0;
                        var weightText = data.HtmlStr.match(/Package\s+Gross\s+Weight[\s\S]*?<div\s+class="[^"]*?bac-item-value[^"]*?\s+[^"]*?fl[^"]*?"[^>]*>\s*([^<]+)/i)?.[1]?.trim();
                        var weightNumber = weightText ? weightText.match(/[\d.]+/g)?.map(Number)[0] || 0 : 0;

                        if (length == 0 || width == 0 || weightNumber == 0) {
                            const sizeMatch2 = data.HtmlStr.match(
                                /Package\s+Size[\s\S]*?<dd\s+class="[^"]*?bac-item-value[^"]*?fl[^"]*?"[^>]*>\s*([\d.]+\s*cm\s*\*\s*[\d.]+\s*cm\s*\*\s*[\d.]+\s*cm)/i
                            );
                            let sizeText2 = null;
                            if (sizeMatch2 && sizeMatch2[1])
                                sizeText2 = sizeMatch2[1].trim();
                            const sizeMatches2 = sizeText2 ? sizeText2.match(/[\d.]+/g)?.map(Number) : [];
                            length = sizeMatches2?.[0] || 0;
                            width = sizeMatches2?.[1] || 0;
                            height = sizeMatches2?.[2] || 0;
                            const weightMatch2 = data.HtmlStr.match(
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
                        t3({ model });
                    }
                    else if (data.Type === "GetMiravia") {
                        const parser = new DOMParser();
                        const doc = parser.parseFromString(data.HtmlStr, 'text/html');
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
                        const firstContainer = doc.querySelector('._6TwhQT0MIk');
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
                        t3({ model });

                    }
                    else if (data.Type === "GetAliexpressRuData") {
                        var paraObj = data.Paras;
                        let skuInfo = "";
                        const descUrl = `https://aliexpress.ru/aer-jsonapi/v1/bx/pdp/web/productData?productId=${paraObj.productId}&sourceId=0&sku_id=${paraObj.skuId}`;
                        try {
                            $.ajax({
                                url: descUrl,
                                method: 'GET',
                                dataType: 'text', // Specify that we expect text data
                                async: false, // Note: Using synchronous requests is deprecated
                                success: function (data) {
                                    skuInfo = data;
                                    t3({ skuInfo });
                                },
                                error: function (jqXHR, textStatus, errorThrown) {
                                    t3({ skuInfo });
                                }
                            });
                        } catch (e) {
                            t3({ skuInfo });
                        }
                    }
                    else if (data.Type === "GetAmazonVariantData") {
                        //请求产品详情页面DOM
                        $.ajax({
                            url: data.SouceUrl,
                            method: 'GET',
                            dataType: 'html',
                            async: false,
                            success: function (pageHtml) {
                                getAmazonVariantData(pageHtml);
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

                            executeRequestsInBatches(dimensionToAsinMap, data)
                                .then(result => {
                                    t3({ variantData: result });
                                })
                                .catch(error => {
                                    t3({ variantData: [] });
                                });
                        }
                        return true;

                    }
                    else if (data.Type === "GetEbayHtmlData" && t3) {
                        var parser = new DOMParser();
                        var doc = parser.parseFromString(data.html, "text/html");
                        var ebayData = getEbayPageData(doc);

                        t3(ebayData || "none");
                        return;
                    }
                    else if (data.Type === "CleanHtmlKeepTags" && t3) {
                        t3({
                            data: cleanHtmlKeepTags(data.HtmlStr)
                        });
                        return;
                    }
                    else if (request.Type === 'CheckCollectionGoodsBtnDisabled') {
                        t3('');
                        return;
                    }
                    else {
                        console.error("未处理的批量采集Type：", data?.Type, data);
                        return;
                    }
                }
                //collectionResNum();
                //setProgress((failUrls.length + successUrls.length + repeatData.length) / collectUrls.length);

                // 只有最终态才刷新进度
                if (
                    data.MessageType === "success" ||
                    data.MessageType === "error" ||
                    data.CollectBoxId
                ) {
                    collectionResNum();
                    setProgress(
                        (failUrls.length + successUrls.length + repeatData.length) / collectUrls.length
                    );
                }

                var stopTime = 0;
                if (isNeedWait) {
                    stopTime = parseInt($("#stopTime").val(), 10) * 1000;
                    stopTime = stopTime > 100 ? stopTime : 100;
                    isNeedWait = false;
                }
                if (index == collectUrls.length - 1) {
                    stopTime = 0;
                }

                const isFinalResult =
                    data.CollectBoxId ||
                    data.MessageType === "success" ||
                    data.MessageType === "error";

                if (!isFinalResult) {
                    // 中间态，直接 return，不推进 index
                    return;
                }

                if (!abortController.signal.aborted) {
                    if (stopTime > 0) {
                        setTimeout(() => {
                            index++;
                            executeNext();
                        }, stopTime);
                    } else {
                        index++;
                        executeNext();
                    }
                }
            });
        } else {
            isNeedWait = false;
            successFun();
        }
    };

    // 开始执行
    executeNext();
    // 返回 AbortController，以便在需要的时候中断操作
    return abortController;
}



// 确认重复采集按钮
$(".popup-confirm").click(function () {
    $('.wyys-main-link').html('');
    $('.copyText').text('');
    $('.div-repeat').hide();
    $('.successNum').text(0);
    $('.errorNum').text(0);
    var repeatChecks = $(".select:checked");
    if (repeatChecks.length == 0) {
        rightTipError('请至少选择一个产品进行采集！');
    } else {
        // 确认选中产品再次进行采集 —— 设置弹出框 —— 进行采集 —— 收集结果
        removeRepeatDataTable();
        addCollectResults();
        setProgress(0);

        var repeatUrls = [];
        for (let i = 0; i < repeatChecks.length; i++) {
            var collectBox = repeatData.filter(x => x.CollectBoxId == $(repeatChecks[i]).attr("data-id"))[0];
            if (collectBox) {
                repeatUrls.push(collectBox.SourceUrl);
            }
        }
        urls = repeatUrls;

        repeatData = [];
        successUrls = [];
        failUrls = [];
        failReasons = [];
        setProgress(0);

        controller = newSyncExecute(repeatUrls, false, () => {
            failToCopy();
            collectionResNum();
        })
    }
});

//执行产品采集逻辑
function BatchExecuteProductAcquisitionLogic(url, isVerifyDuplicate, signal, funCallback) {
    try {
        //匹配平台
        var platformData = MatchingPlatform(url);
        var platformId = platformData.PlatformId;
        if (!supportPlatforms.some(x => x === platformId)) {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "该平台暂不支持批量采集！" })
            return;
        }
        if (platformId > 0) {
            if (isVerifyDuplicate) {
                GetSourceUrlEntity(url,
                    function (sku) {     // 获取采集过的产品数据成功的回调 —— successfulCallBack
                        if (sku !== null) {
                            funCallback(sku)
                        } else {
                            AnalyticalProducts(platformId, {
                                isLinkCollect: true,
                                isBathCollect: true
                            }, null, url, funCallback);
                        }
                    },
                    function (msg) {
                        // 获取采集过的产品数据失败的回调 —— failedCallBack
                        errorTip(msg)
                    }
                );
            } else {
                AnalyticalProducts(platformId, { isLinkCollect: true, isBathCollect: true }, null, url, funCallback);
            }
        } else {
            throw new Error("产品采集失败!");
        }
    } catch (error) {
        var errorMsg = { "Type": "Alter", "MessageType": "error", "Message": "采集地址无效，或不支持该网址采集。" }
        funCallback(errorMsg)
        // removeCollectResults()
        // if ($('#urlCollect').val()) {
        //     errorTip('采集地址无效，或不支持该网址采集。')
        // }
    }
}

// 采集过的产品数据
function GetSourceUrlEntity(sourceUrl, successfulCallBack, failedCallBack) {
    request(config.url.getSourceUrlEntity(), {
        responseType: "json",
        body: { "SourceUrl": sourceUrl },
        method: "POST"
    }).then(res => {
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

// 右侧弹框提示
function rightTipError(err) {
    GrowlNotification.notify({
        title: '无忧易售',
        image: { visible: true, customImage: config.logoBase64 },
        description: err,
        type: 'error',
        position: 'top-right',
        closeTimeout: 3000,
    });
}

function rightTipSuccess(success) {
    GrowlNotification.notify({
        title: '无忧易售',
        image: { visible: true, customImage: config.logoBase64 },
        description: success,
        type: 'success',
        position: 'top-right',
        closeTimeout: 1500,
    });
}

// 添加重复采集的表格
function addRepeatDataTable() {
    $(".popup").addClass("visible");
    $(".popup-mask").addClass("visible");
}

// 移除重复采集的表格
function removeRepeatDataTable() {
    $(".popup").removeClass("visible");
    $(".popup-mask").removeClass("visible");
}

// 添加采集结果提示框
function addCollectResults() {
    $(".collect_results").addClass("visible");
    $(".popup-mask").addClass("visible");
}

// 移除采集结果提示框
function removeCollectResults() {
    $(".collect_results").removeClass("visible");
    $(".popup-mask").removeClass("visible");
}

// 渲染失败采集链接
function failToCopy() {
    if (failUrls.length > 0) {
        $('.copyText').text('复制失败链接')
        $('div.wyys-main-link').html('');
        for (i = 0; i < failUrls.length; i++) {
            var a = $("<a>").text(failUrls[i]).addClass('failUrl');
            var reasons = failReasons[i].replace('执行失败，', '');
            var p = $("<p>").text(reasons).addClass('reasonP');
            $("div.wyys-main-link").append(p);
            $("div.wyys-main-link").append(a);
        }
    }
}

// 渲染采集结果数量
function collectionResNum() {
    $('.successNum').text(successUrls.length)
    $('.errorNum').text(failUrls.length)
    $('.repeatNum').text(repeatData.length)
}

// 采集结果弹出框关闭按钮
$(".collect_results-no, .collect_results-close").click(function () {
    removeCollectResults()
    if (failUrls.length == 0) {
        $('#urlCollect').val('');
    }
    $('div.wyys-main-link').html('');
    setProgress(0);
    controller.abort();
});

// 重复采集表格弹出框关闭按钮
$(".popup-close").click(function () {
    $(".popup").removeClass("visible");
    $(".popup-mask").removeClass("visible");
});
// 重复采集时点击跳过
$(".popup-cancel").click(function () {
    $(".popup").removeClass("visible");
    $(".collect_results").addClass("visible");
    setProgress(1)
    collectionResNum()
});
// 重复采集时的弹出框——全选/取消全选
$("#selectAll").click(function () {
    var allChecked = $(this).prop("checked");
    $(".select").prop("checked", allChecked);
});
// 回到首页
$("#toHome").click(function () {
    window.open(config.url.domain());
});
$("#showCollected").click(function () {
    window.open(config.url.domain() + '/main#/collectbox');
})
// 输入框置空
$('#reset').click(function () {
    $('#urlCollect').val('')
    removeErrorStyle();
})
// 复制采集失败的链接
$('.copyText').click(function () {
    // 获取要复制的文本
    // var textToCopy = $("div.link a").text();
    var textToCopy = $("div.wyys-main-link a").map(function () {
        return $(this).text();
    }).get().join('\n');
    // 创建一个临时文本区域
    var tempTextArea = $("<textarea>");
    // 将要复制的文本添加到文本区域中
    tempTextArea.text(textToCopy);
    // 将文本区域添加到文档中
    $("body").append(tempTextArea);
    // 选中文本区域中的文本
    tempTextArea.select();
    try {
        // 尝试将选中的文本复制到剪贴板
        document.execCommand("copy");
        // 复制成功，弹出成功提示框
        rightTipSuccess("复制成功!")
    } catch (err) {
        rightTipError('复制失败，请手动复制!')
    }
    // 删除临时文本区域
    tempTextArea.remove();
})

function select() {
    var allChecked = $(".select:checked").length === $(".select").length;
    $("#selectAll").prop("checked", allChecked);
}

// 框底提示错误信息
function errorTip(errorInfo) {
    $("#errorMessage").addClass("visible");
    $("#urlCollect").addClass("visible");
    $("#errorMessage").text(errorInfo)
}

// 框底移除提示错误信息
function removeErrorStyle() {
    $("#errorMessage").removeClass("visible");
    $("#urlCollect").removeClass("visible");
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

// 提取 Mercado 链接中的商品标识，用于判断广告链接、变体链接、详情页链接是否指向同一个商品。
function collectMercadoProductTokens(rawUrl) {
    var tokens = [];
    if (!rawUrl) {
        return tokens;
    }

    try {
        var url = new URL(rawUrl);
        var pushMatches = function (text) {
            if (!text) {
                return;
            }

            var matches = String(text).match(/MLM[A-Z0-9]+|ML[A-Z]{1,3}[A-Z0-9]+/g);
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
function isSameMercadoProductUrl(firstUrl, secondUrl) {
    try {
        var first = new URL(firstUrl);
        var second = new URL(secondUrl);
        if (first.origin !== second.origin) {
            return false;
        }

        if (first.pathname === second.pathname) {
            return true;
        }

        var firstTokens = collectMercadoProductTokens(firstUrl);
        var secondTokens = collectMercadoProductTokens(secondUrl);
        return firstTokens.length > 0 && secondTokens.some(function (item) {
            return firstTokens.includes(item);
        });
    } catch (e) {
        return false;
    }
}

// Mercado 后台 fetch 容易返回验证码安全页，这里改为请求 background 打开真实商品页标签，再从页面 DOM 获取 HTML。
function proxyFetchMercadoHtml(requestUrl, callback) {
    chrome.runtime.sendMessage({ Type: "GetMercadoHtmlByTab", RequestUrl: requestUrl }, function (res) {
        if (chrome.runtime.lastError) {
            callback({ IsSuccess: false, Data: chrome.runtime.lastError.message });
            return;
        }

        callback(res || { IsSuccess: false, Data: "未获取到Mercado页面HTML" });
    });
}

// 获取 Mercado 商品页 HTML：优先复用当前活动商品页 DOM；如果当前页不是目标商品，则走临时标签页获取。
function getMercadoHtml(requestUrl, callback) {
    chrome.tabs.query({ active: true, currentWindow: true }, function (tabs) {
        var activeTab = tabs && tabs.length > 0 ? tabs[0] : null;
        if (!activeTab || !activeTab.id || !activeTab.url || !isSameMercadoProductUrl(requestUrl, activeTab.url)) {
            proxyFetchMercadoHtml(requestUrl, callback);
            return;
        }

        chrome.tabs.sendMessage(activeTab.id, { Type: "GetMercadoHtml", RequestUrl: requestUrl }, function (response) {
            if (chrome.runtime.lastError || !response || !response.IsSuccess) {
                proxyFetchMercadoHtml(requestUrl, callback);
                return;
            }

            callback(response);
        });
    });
}