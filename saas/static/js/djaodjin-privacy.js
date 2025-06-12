/**
   Functionality related to privacy policies.
 */

/* global getMetaCSRFToken showErrorMessages */

(function (root, factory) {
    if (typeof define === 'function' && define.amd) {
        // AMD. Register as an anonymous module.
        define(['exports', 'http'], factory);
    } else if (typeof exports === 'object' && typeof exports.nodeName !== 'string') {
        // CommonJS
        factory(exports, require('http'));
    } else {
        // Browser true globals added to `window`.
        factory(root, root.http);
        // If we want to put the exports in a namespace, use the following line
        // instead.
        // factory((root.djResources = {}), root.http);
    }
}(typeof self !== 'undefined' ? self : this, function (exports, http) {


function updatePrivacySettings(elemId, value) {
    let data = {};
    data[elemId] = value;
    http.post('/legal/privacy', data);
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
    }

    if (document.readyState !== 'loading') {
        onDocumentReady();
    } else {
        document.addEventListener('DOMContentLoaded', onDocumentReady);
    }

}));
