casper.test.comment('Update card - sunny');
var helper = require('./vendor/djangocasper.js');
helper.scenario('/saas/billing/abc/card',
    function() {
        this.evaluate(function(){
        document.querySelector('#card-number').value = '4242424242424242';
        document.querySelector('#card-exp-month').value = '12';
        document.querySelector('#card-exp-year').value = '2014';
        document.querySelector('#card-cvc').value = '123';
        });
        this.fill('form#payment-form', {
            'card_name':           'Big Boss',
            'card_address_line1': '1 ABC loop',
            'card_city': 'San Francisco',
            'card_address_state':       'CA',
            'card_address_zip':       '94102',
            'card_address_country':     'USA'
        }, true);
    },
    function() {
        this.evaluateOrDie(function() {
            return 'XXX-4242'.test(this.getPageContent())
        }, 'Update sucessful');
    }
);
helper.run();
