/**
   Functionality related to privacy policies.
 */

/* uses exports from djaodjin-resources.js: http */

(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        // AMD. Register as an anonymous module.
        define(['exports'], factory);
    } else if (typeof exports === 'object' && typeof exports.nodeName !== 'string') {
        // CommonJS
        factory(exports);
    } else {
        // Browser true globals added to `window`.
        factory(root);
        // If we want to put the exports in a namespace, use the following line
        // instead.
        // factory((root.djResources = {}));
    }
}(typeof self !== 'undefined' ? self : this, function (exports) {

const COOKIE_BANNER_ID = "cookie-banner";

function enableTrackingScripts(event) {
    var banner = document.getElementById(COOKIE_BANNER_ID);
    banner.style.display = "none";
    let data = {};
    for( const key in PRIVACY_COOKIES_ENABLED ) {
        data[key] = true;
    }
    http.post('/legal/privacy', data);
    for( const key in PRIVACY_COOKIES_ENABLED ) {
        if( PRIVACY_COOKIES_ENABLED[key] ) {
            PRIVACY_COOKIES_ENABLED[key]();
        }
    }
}

function disableTrackingScripts(event) {
    var banner = document.getElementById(COOKIE_BANNER_ID);
    banner.style.display = "none";
    let data = {};
    for( const key in PRIVACY_COOKIES_ENABLED ) {
        data[key] = false;
    }
    http.post('/legal/privacy', data);
}


function updatePrivacySettings(key, value) {
    let data = {};
    data[key] = value;
    http.post('/legal/privacy', data);
    if( value && PRIVACY_COOKIES_ENABLED[elemId] ) {
        PRIVACY_COOKIES_ENABLED[key]();
    }
}


    // attach properties to the exports object to define
    // the exported module properties.
    exports.updatePrivacySettings = updatePrivacySettings;

    // code run when the document is ready.
    function onDocumentReady() {
        const elements = document.querySelectorAll('.privacy-setting');
        elements.forEach(function(elem) {
            const elemId = elem.id;
            if( elemId ) {
                elem.addEventListener('change', function(event) {
                    updatePrivacySettings(elemId, event.target.checked);
                });
            }
        });

        // toggle cookie banner off
        try {
            var btnDisable = document.getElementById(
                COOKIE_BANNER_ID).getElementsByTagName('button')[0];
            btnDisable.addEventListener("click", disableTrackingScripts);
        } catch( TypeError ) {
        }
        try {
            var btnEnable = document.getElementById(
                COOKIE_BANNER_ID).getElementsByTagName('button')[1];
            btnEnable.addEventListener("click", enableTrackingScripts);
        } catch( TypeError ) {
        }
    }

    if (document.readyState !== 'loading') {
        onDocumentReady();
    } else {
        document.addEventListener('DOMContentLoaded', onDocumentReady);
    }

}));
