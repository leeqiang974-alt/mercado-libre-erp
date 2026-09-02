//调用服务器接口
var CATEGORY_SAVE_LIMIT_MESSAGE = '添加失败，采集箱数量保存上限100万行，请删除已认领或过期数据。';

// ERP recollection tabs carry this marker in the Amazon URL. Close only after
// the legacy save endpoint explicitly confirms success; ordinary extension
// collection and every failure path keep the source page open.
function closeErpRecollectionTabAfterSave(tab) {
    if (!tab || !tab.id || !tab.url || !/#[^#]*meli-recollect-source=\d+/.test(tab.url)) {
        return;
    }
    if (typeof chrome === 'undefined' || !chrome.tabs || typeof chrome.tabs.remove !== 'function') {
        return;
    }
    chrome.tabs.remove(tab.id, function () {
        void chrome.runtime.lastError;
    });
}

function SaveProduct(tab, requestBody, funCallback) {
    request(config.url.saveProduct(), {
        responseType: "json"
        , body: requestBody
        , method: "POST"
    }).then(res => {
        if (res !== null) {
            if (res.IsSuccess === true) {
                funCallback({ "Type": "Alter", "MessageType": "success", "Message": "产品采集成功" }, tab, function (response) { });
                closeErpRecollectionTabAfterSave(tab);
            } else {
                var msg = res.Message == null ? (res.ResponseError == null ? "服务器未知异常，请联系管理员" : res.ResponseError.Message) : res.Message;

                var actionUrl = res.Url && res.Url != null ? res.Url : '';
                if (actionUrl != '' && actionUrl.indexOf('http') === -1)
                    actionUrl = config.url.domain + actionUrl;

                var actionBtnText = '';
                if (msg.indexOf('授权') > -1)
                    actionBtnText = '去授权';
                else if (msg.indexOf('升级插件') > -1)
                    actionBtnText = '去升级';

                if (msg === CATEGORY_SAVE_LIMIT_MESSAGE) {
                    funCallback({ "Type": "Alter", "MessageType": "error", "Message": msg }, tab, function (response) { });
                } else {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "产品采集失败！原因：" + msg, "Url": actionUrl, "ActionBtnText": actionBtnText }, tab, function (response) { });
                }
            }
        } else {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "发生未知异常！请稍后重试！若长时间发生此错误，请与客服联系！" }, tab, function (response) { });
        }
    }).then(data => {
        funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
    }).catch(reason => {
        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "服务器连接失败！请稍后重试！若长时间发生此错误，请与客服联系！" }, tab, function (response) { });
        funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
    });
}


function SaveLiknProduct(tab, data, funCallback) {
    request(config.url.saveCollectProduct(), {
        responseType: "json"
        , body: data
        , method: "POST"
    }).then(res => {
        if (res !== null) {
            if (res.IsSuccess === true) {
                funCallback({ "Type": "Alter", "MessageType": "success", "Message": "产品采集成功" }, tab, function (response) { });
                closeErpRecollectionTabAfterSave(tab);
            } else {
                let msg = res.Message == null ? (res.ResponseError == null ? "服务器未知异常，请联系管理员" : res.ResponseError.Message) : res.Message;

                let actionUrl = res.Url && true ? res.Url : '';
                if (actionUrl !== '' && actionUrl.indexOf('http') === -1)
                    actionUrl = config.url.domain() + actionUrl;

                let actionBtnText = '';
                if (msg.indexOf('授权') > -1)
                    actionBtnText = '去授权';
                else if (msg.indexOf('升级插件') > -1)
                    actionBtnText = '去升级';

                if (msg === CATEGORY_SAVE_LIMIT_MESSAGE) {
                    funCallback({ "Type": "Alter", "MessageType": "error", "Message": msg }, tab, function (response) { });
                } else {
                funCallback({ "Type": "Alter", "MessageType": "error", "Message": "产品采集失败！原因：" + msg, "Url": actionUrl, "ActionBtnText": actionBtnText }, tab, function (response) { });
                }
            }
        } else {
            funCallback({ "Type": "Alter", "MessageType": "error", "Message": "发生未知异常！请稍后重试！若长时间发生此错误，请与客服联系！" }, tab, function (response) { });
        }
    }).then(data => {
        funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
    }).catch(reason => {
        funCallback({ "Type": "Alter", "MessageType": "error", "Message": "服务器连接失败！请稍后重试！若长时间发生此错误，请与客服联系！" }, tab, function (response) { });
        funCallback({ "Type": "CheckCollectionGoodsBtnDisabled", "Disabled": false }, tab, function (response) { });
    });
}

//单张图片上传
function UploadImage(imageUrl, callback) {
    request(config.url.uploadImage(), {
        responseType: "json"
        , body: {
            "imageUrls": [imageUrl],
            "isTemp": true
        }
        , method: "POST"
    }).then(res => {
        if (res !== null) {
            if (res.IsSuccess === true) {
                callback(res.Url);
            } else {
                callback(imageUrl);
            }
        } else {
            callback(imageUrl);
        }
    }).catch(reason => {
        callback(imageUrl);
    });
}

//验证采集重复
function VerifyDuplicate(sourceUrl, successfulCallBack, failedCallBack) {
    request(config.url.verifyDuplicate(), {
        responseType: "json"
        , body: {
            "SourceUrl": sourceUrl
        }
        , method: "POST"
    }).then(res => {
        if (res !== null) {
            if (res.IsSuccess === true) {
                successfulCallBack(res.Data.ParentSku);
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
