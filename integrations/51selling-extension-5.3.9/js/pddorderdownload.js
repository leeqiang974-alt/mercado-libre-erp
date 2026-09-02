// 监听backgroud的消息
chrome.runtime.onMessage.addListener(pddOrderReceiveMessages);

function pddOrderReceiveMessages(request, sender, sendResponse) {
    if (request.Type === "GetPDDUserName") {
        $.ajax({
            type: "GET",
            url: "https://mobile.yangkeduo.com/proxy/api/api/apollo/v3/user/me?pdduid=" + request.Data.userId,
            async: false,
            contentType: "application/json",
            dataType: "text",
            headers: {
                withCredentials: true
            },
            success: function (data) {
                let response = JSON.parse(data);
                windowOpenerPostMessage({ "Type": "PddUserInfo", "UserId": request.Data.userId, "UserName": response.nickname }, '*');
            },
            error: function (data) {
                windowOpenerPostMessage({ "Type": "ErrorMsg", "Message": '拼多多账号获取失败，请先登录拼多多账号并开启采集插件后重试' });
            }
        });
    }
    else if (request.Type === "GetPDDProductInfo") {
        //先抓取Json数据，没有在调用API
        const scripts = document.getElementsByTagName("script");
        for (let script of scripts) {
            const content = script.textContent || "";
            if (content.includes("window.rawData=")) {
                // 提取 window.rawData= 后面的值 
                let jsonStr = content.replace("window.rawData=", "var jsonData=")
                let interpreter = new eval5.Interpreter(window);
                interpreter.evaluate(jsonStr); 
                break; // 找到第一个 window.rawData= 就可以停止
            }
        }
        if (jsonData?.store?.initDataObj?.goods && jsonData.store.initDataObj.goods.skus.length > 0 && jsonData.store.initDataObj.goods.skus.find(x => x.specs && x.specs.length > 0))
            windowOpenerPostMessage({ "Type": "PddProductInfo", "Source": "Json", "Url": location.href, Data: jsonData.store.initDataObj.goods });
        else {
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
                    windowOpenerPostMessage({ "Type": "PddProductInfo", "Source": "API", "Url": location.href, Data: response });
                })
                .catch(response => {
                    windowOpenerPostMessage({ "Type": "ErrorMsg", "Message": "获取PDD产品信息失败:" + JSON.stringify(response) })
                });
        }        
    }
    else if (request.Type === "PDDOrderDownload") {
        let orderDownloadCount = 1;
        let currentUrl = new URL(location.href).searchParams; 
        let code = currentUrl.get("PurchaseOrderCode"); 

        const scripts = document.getElementsByTagName("script");
        for (let script of scripts) {
            const content = script.textContent || "";
            if (content.includes("window.rawData=")) {
                // 提取 window.rawData= 后面的值 
                let jsonStr = content.replace("window.rawData=", "var jsonData=")
                let interpreter = new eval5.Interpreter(window);
                interpreter.evaluate(jsonStr); 
                break; // 找到第一个 window.rawData= 就可以停止
            }
        }

        let goods_list = JSON.parse(currentUrl.get("goods_list")) 
        if (jsonData?.store?.cartInfo && jsonData.store.cartInfo.useless && jsonData.store.cartInfo.useless.length > 0 ||
            (jsonData?.store?.cartInfo && jsonData.store.cartInfo.available.filter(x => goods_list.find(w =>
                x.goodsInfo.find(z => z.skuId == w.sku_id) && x.goodsInfo.find(z => z.skuId == w.sku_id).goodsLimitNumber < w.goods_number)).length > 0))
        {           
            windowOpenerPostMessage({ "Type": "ErrorMsg", "Message": `${code} 下单失败，产品库存不足`})
            return;
        }    
        if(jsonData?.store?.goodsItemStore && jsonData?.store?.goodsItemStore.increaseDisable && jsonData?.store?.goodsItemStore.goodsNumber == jsonData?.store?.goodsItemStore.finalLimitNumber)
        {   
            let inputNumber = currentUrl.get("goods_number");
            if(inputNumber > jsonData?.store?.goodsItemStore.goodsNumber)
            {
                windowOpenerPostMessage({ "Type": "ErrorMsg", "Message": `${code} 下单失败，产品库存不足`})
                return;
            }
        }          
        $("span,div").each(function () {
            if ($(this).text().indexOf('优惠') >= 0) {
                //打开优惠
                $(this).closest("div").click();
            }
        });
        //领取优惠 
        new Promise((resolve) => {
            setTimeout(() => {
                let isClaim = 0;
                try {
                    $("span,div").each(function () {
                        if ($(this).text().indexOf('再领取') > -1 || $(this).text().indexOf('领取') > -1 || $(this).text().indexOf('关注并领取') > -1) {
                            $(this).closest("div").click(); 
                            isClaim = 1;
                        }
                    });
                } catch (e) { 

                }
                setTimeout(() => {
                    $("span,div").each(function () {
                        if ($(this).text().indexOf('再领取') > -1 || $(this).text().indexOf('领取') > -1 || $(this).text().indexOf('关注并领取') > -1) {
                            $(this).closest("div").click();
                            isClaim = 1;
                        }
                    });
                    if (isClaim == 0 && $('div[aria-label="关闭"][role="button"]'))//兼容特殊优惠无需领取效果
                        $('div[aria-label="关闭"][role="button"]').click(); 
                    resolve(); // 触发 then()
                }, 300);
            }, 300);
        }).then(() => {//下单
            let pageUnloadedIndex = 0;
            setTimeout(() => {
                $("span,div").each(function () {
                    if ("微信支付" === $(this).text() && orderDownloadCount === 1) { 
                        orderDownloadCount = 0;
                        //选择微信支付
                        $(this).closest("div").click();
                        //下单
                        $("div[aria-label=立即支付]").click();
                        //兼容平台按钮错误问题
                        let payButton = $('div[data-active="red"][role="button"]');
                        if (payButton && payButton.text().indexOf('立即支付') > -1)                        
                            payButton.click();                        
                        if (pageUnloadedIndex == 0) {
                            pageUnloadedIndex = 1;
                            // 2. 设置一个标志，表示页面“尚未关闭”
                            let pageUnloaded = false;
                            // 3. 监听页面卸载事件（关闭、跳转、刷新）
                            const handleUnload = () => {
                                pageUnloaded = true;
                            };
                            window.addEventListener('beforeunload', handleUnload, { once: true });
                            // 补充监听 pagehide（对 iOS Safari 和部分缓存导航更可靠）
                            window.addEventListener('pagehide', handleUnload, { once: true });
                            // 4. 3 秒后检查
                            setTimeout(() => {
                                if (!pageUnloaded) {
                                    windowOpenerPostMessage({ "Type": "ErrorMsg", "Message": "拼多多下单失败，先跳过该订单，继续后面订单下单" });
                                }
                                // 清理监听（虽然用了 {once: true}，但双重保险）
                                window.removeEventListener('beforeunload', handleUnload);
                                window.removeEventListener('pagehide', handleUnload);
                            }, 3000);
                        }
                    }
                });

                $("p").each(function () {
                    if ("当前访问人数较多，排队中" === $(this).text()) {                        
                        if (pageUnloadedIndex == 0) {
                            pageUnloadedIndex = 1;
                            // 2. 设置一个标志，表示页面“尚未关闭”
                            let pageUnloaded = false;
                            // 3. 监听页面卸载事件（关闭、跳转、刷新）
                            const handleUnload = () => {
                                pageUnloaded = true;
                            };
                            window.addEventListener('beforeunload', handleUnload, { once: true });
                            // 补充监听 pagehide（对 iOS Safari 和部分缓存导航更可靠）
                            window.addEventListener('pagehide', handleUnload, { once: true });
                            // 4. 3 秒后检查
                            setTimeout(() => {
                                if (!pageUnloaded) {
                                    windowOpenerPostMessage({ "Type": "ErrorMsg", "Message": "拼多多下单失败，先跳过该订单，继续后面订单下单" });
                                }
                                // 清理监听（虽然用了 {once: true}，但双重保险）
                                window.removeEventListener('beforeunload', handleUnload);
                                window.removeEventListener('pagehide', handleUnload);
                            }, 1000);
                        }
                    }
                });
            }, 1000);
        });   
    }
    else if (request.Type === "BacklinkOrderDownloadInfo") {
        let userId = getCookie('pdd_user_id');
        let url = new URL(request.Url)
        let req = {
            "option_json": url.searchParams.get("option_json"),
            "order_sn": url.searchParams.get("order_sn"),
            "order_amount": url.searchParams.get("order_amount"),
            "goods_id": url.searchParams.get("goods_id"),
            "userId": userId
        }
        windowOpenerPostMessage({ "Type": "BacklinkOrderDownloadInfo", "Data": req })
    }
    else if (request.Type === "GetPDDOrderInfo") { 
        let scripts = $('script');
        let userId = getCookie('pdd_user_id');
        for (let sp in scripts) {
            let content = scripts[sp].textContent || scripts[sp].innerText || $(scripts[sp]).text();

            if (content && content.includes('window.rawData=')) {
                // 更精确的正则匹配
                let regex = /window\.rawData\s*=\s*({[\s\S]*?})(?:\s*;|$)/;
                let match = content.match(regex);

                if (match && match[1]) {
                    try { 
                        let data = JSON.parse(match[1]);
                        data['userid'] = userId;
                        windowOpenerPostMessage({ "Type": "OrderInfo", "Data": data });
                        return false;
                    } catch (error) { 
                        // 尝试修复常见的 JSON 格式问题
                        try {
                            let fixedJson = match[1]
                                .replace(/(['"])?([a-zA-Z0-9_]+)(['"])?:/g, '"$2":') // 修复键名引号
                                .replace(/,(\s*[}\]])/g, '$1'); // 修复尾随逗号                                 
                            let data = JSON.parse(fixedJson);
                            data['userid'] = userId;
                            windowOpenerPostMessage({ "Type": "OrderInfo", "Data": data });
                            return false;
                        } catch (e) {
                            windowOpenerPostMessage({ "Type": "ErrorMsg", "Data": e });
                            return false;
                        }
                    }
                }
            }
        }
    }
    else if (request.Type === "GetPDDOrderList") { 
        let cookie = document.cookie;
        let userId = getCookie('pdd_user_id');
        let url = 'https://mobile.yangkeduo.com/proxy/api/api/aristotle/order_list_v3?pdduid=' + userId;
        let offset = '';
        let isStop = false;
        let timestampSec = Math.floor(new Date(new Date().getTime() - 3 * 24 * 60 * 60 * 1000).getTime() / 1000);   

        let headers = {
            'Cookie': cookie,
            'Content-Type': 'application/json'
        };

        let orderList = [];

        async function performAsyncTask(s) {
            let data = {
                type: 'all',
                page: 1,
                origin_host_name: 'mobile.yangkeduo.com',
                scene: 'order_list_h5',
                page_from: 0,
                pay_front_supports: [],
                anti_content: '',
                size: 10,
                offset: offset
            };

            fetch(url, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(data),
                credentials: 'include' // 如果需要携带cookie，可以加上这个选项
            })
                .then(response => response.json())
                .then(response => {
                    for (var i = 0; i < response.orders.length; i++) {
                        response.orders[i]['userid'] = userId;
                        orderList.push(response.orders[i])
                    }                    
                    if (response.orders.length < 10 || response.orders.find(x => x.order_time < timestampSec)) {
                        windowOpenerPostMessage({ "Type": "GetPDDOrderList", Data: orderList });
                        isStop = true;
                        return false;
                    }
                    else
                        offset = response.offset;
                })
                .catch(error => {
                    windowOpenerPostMessage({ "Type": "ErrorMsg", "Message": "获取PDD订单列表失败:" + JSON.stringify(error) })
                    isStop = true;
                    return false;
                });

            // 模拟异步操作
            await new Promise(resolve => setTimeout(resolve, s));
        }

        let intervalId = setInterval(async () => {
            try {
                await performAsyncTask(500);
                if (isStop)
                    clearInterval(intervalId);
            } catch (error) {
                windowOpenerPostMessage({ "Type": "ErrorMsg", "Message": "获取PDD订单列表失败:" + JSON.stringify(error) })
                clearInterval(intervalId);
            }
        }, 1500);
    }
    else if (request.Type === "WindowOpenerPostMessage") {
        windowOpenerPostMessage(request.Message);
    }
}


// 向父页面发送消息
// 目前用于和erp进行js交互
function windowOpenerPostMessage(message) {
    if (message && window && window.opener && window.opener.postMessage)
        window.opener.postMessage(message, '*');
} 