/**
 * �Ƿ�����ͨ���� ��Object��ֱ��ʵ����
 * @param {*} obj
 * @returns
 */
const isPlainObject = (obj) => {
    let proto, Ctor;
    if (!obj ||
        Object.prototype.toString.call(obj) !== "[object Object]")
        return false;
    proto = Object.getPrototypeOf(obj);
    if (!proto) return true;
    Ctor = proto.hasOwnProperty("constructor") && proto.constructor;
    return typeof Ctor === "function" && Ctor === Object;
};

// ��ʼ��Ĭ������
let initialConfig = {
    method: "GET",
    params: null,// getϵ������ʹ��
    body: null,// postϵ������ʹ�� getϵ�����󲻿ɴ�body������
    headers: {
        "content-type": "application/json"
    }, // ����ͷ��Ϣ
    catch: "no-cache",// ���󲻻���
    credentials: "include", // ����Я����Ϣ cookie��
    responseType: "json", // ��Ӧ�����ݸ�ʽ
};

const request = function request(url, config) {
    // init params
    if (typeof url !== "string")
        throw new TypeError("url must be required and of string type!");
    // ���Ǵ�����
    if (!isPlainObject(config)) config = {};
    // �ϲ�������(����Ӧ������ϲ�����Ҫʹ��assign����)
    config = Object.assign({}, initialConfig, config);
    // handle url
    //if (/^http(s?):\/\//i.test(url)) url = baseURL + url;
    let { method, params, body, headers, cache, credentials, responseType } = config;
    // handle params 
    if (params != null) {
        if (isPlainObject(params)) {
            // תΪ name=zs&age=12 �����ַ���ƴ����ȥ(ʹ��qs�����)
            let p = "";
            for (const key in params) {
                p += (key + "=" + params[key] + "&");
            }
            params = p.slice(0, -1);
        }
        url += `${url.includes("?") ? "&" : "?"}${params}`;
    }
    // handle body
    if (isPlainObject(body)) {
        body = JSON.stringify(body);
    } else if (typeof body === "string") {
        try {
            JSON.parse(body);
            // ��json�ַ��� Ĭ�Ͼ���json��������
        } catch (error) {
            // ����JSON�ַ���
            // ��������ͷ
            headers["content-type"] = "application/x-www-form-urlencoded";
        }
    }
    // common info
    // �������������� ��������ǰЯ��token
    //let token = "token";
    //if (token) {
    //    headers["Authorization"] = `Bearer ${token}`;
    //}
    // ����config
    config = {
        method: method.toUpperCase(),
        headers,
        credentials,
        cache,
    }
    if (/^POST|PUT|PATCH$/.test(method) && body != null) config.body = body;
    return fetch(url, config).then(response => {
        let { status, statusText } = response;
        
        // ֻ��״̬������ 2 ���� 3 ��ʼ �ű�ʾ����ɹ�
        if (status >= 200 && status < 400) {
            let result;
            switch (responseType.toUpperCase()) {
                case "JSON":
                    result = response.json();
                    break;
                case "TEXT":
                    var contentType = response.headers.get("content-type");
                    if (contentType.toUpperCase().indexOf("GB18030") >= 0) {
                        return response.arrayBuffer().then(buffer => {
                            const decoder = new TextDecoder("gbk");
                            const text = decoder.decode(buffer);
                            return text;
                        })
                    } else {
                        result = response.text();
                    }
                    break;
                case "BLOB":
                    result = response.blob();
                    break;
                case "ARRAYBUFFER":
                    result = response.arrayBuffer();
                    break;
                default: // ����ƥ�� תjson
                    result = response.json();
                    break;
            }
            return result;
        }
        // ����ʧ��
        return Promise.reject({
            code: "STATUS ERROR",
            status,
            statusText
        });
    }).catch(reason => {
        // ʧ�����
        // @1. ״̬�����
        if (reason && reason.code === "STATUS ERROR") {
            switch (reason.status) {
                case 400:
                    break;
                case 401:
                    break;
                case 402:
                    break;
                case 403:
                    break;
                case 500:
                    break;
                default:
                    break;
            }
        }
        // @2. �����ж� 
        else if (!navigator.onLine) { }
        // @3 �������� ��������ֹ ȡ����
        else { }
        return Promise.reject(reason);
    });
};


