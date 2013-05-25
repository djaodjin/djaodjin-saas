casper.test.comment('Update card - sunny');

casper.on('remote.message', function(msg) {
    this.echo('remote message caught: ' + msg);
})

var helper = require('./vendor/djangocasper.js');
helper.scenario('/saas/billing/abc/card',
    function() {
        this.evaluate(function(){
            /* For PCI compliance, we don't want the card-number, expiration
               date and cvc to hit our website. This means there is no "name"
               fields on the input node in the DOM for those.
               Thus we run querySelector() and click() in an evaluate block
               instead of using fill() to submit the form.
             */
            document.querySelector('#card-number').value = '4242424242424242';
            document.querySelector('#card-exp-month').value = '12';
            document.querySelector('#card-exp-year').value = '2014';
            document.querySelector('#card-cvc').value = '123';
            document.querySelector("#payment-form [name='card_name']").value = 'Big Boss';
            document.querySelector("#payment-form [name='card_address_line1']").value = '1 ABC loop';
            document.querySelector("#payment-form [name='card_city']").value = 'San Francisco';
            document.querySelector("#payment-form [name='card_address_state']").value = 'CA';
            document.querySelector("#payment-form [name='card_address_zip']").value = '94102';
            document.querySelector("#payment-form [name='card_address_country']").value = 'USA';
            document.querySelector(".payment-submit").click()
        });
        this.waitFor(function check() {
            return this.getCurrentUrl() == 'http://localhost:8081/saas/billing/abc'
        });
    },
    function() {
        this.test.assertUrlMatch(/\/saas\/billing\/abc$/, 'on billing page');
        this.test.assertTextExists('XXX-4242', 'card was updated');
    }
);
helper.run();
