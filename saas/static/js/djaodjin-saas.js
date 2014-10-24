/* Functionality related to the SaaS API.
 */
(function ($) {

    /* invoice */
    function Invoice(el, options){
        this.element = $(el);
        this.options = options;
        this._init();
    }

    Invoice.prototype = {
        _init: function () {
            var self = this;

            self.element.find('input:radio').change(function() {
                self.updateTotalAmount();
            });

            self.element.find('.add-seat').click(function(event) {
                event.preventDefault();
                var subscription = $(this).parents('tbody');
                var prevLine = $(this).parents('tr').prev();
                var seatFirstName = $('.seat-first-name');
                var seatLastName = $('.seat-last-name');
                var seatEmail = $('.seat-email');
                var item = new CartItem({
                    'plan': subscription.attr('data-plan'),
                    'first_name': seatFirstName.val(),
                    'last_name': seatLastName.val(),
                    'email': seatEmail.val(),
                    'urls': { 'saas_api_cart': self.options.saas_api_cart }});
                seatFirstName.val('');
                seatLastName.val('');
                seatEmail.val('');
                item.add(function(data, textStatus, jqXHR) {
                    var msg = data.first_name + " " + data.last_name
                        + " (" + data.email + ")";
                    var newLine = prevLine;
                    if( jqXHR.status == 201 ) {
                        newLine = prevLine.clone();
                        prevLine.removeClass('highlight');
                        var descrNode = $(newLine.children('td')[2]);
                        descrNode.text(descrNode.text().replace(
                                /, for .*/, ", for " + msg));
                        newLine.insertAfter(prevLine);
                    } else {
                        var descrNode = $(newLine.children('td')[2]);
                        descrNode.text(descrNode.text() + ", for " + msg);
                    }
                    newLine.addClass('highlight');
                    self.updateTotalAmount();
                }, function(result) {
                    var msgs = [];
                    for( var field in result.responseJSON ) {
                        msgs = msgs.concat(result.responseJSON[field]);
                    }
                    if( !(msgs.length > 0) ) {
                        msgs = ['ERROR ' + result.status + ': ' + result.statusText];
                    }
                    showMessages(msgs, 'danger');
                });
                return false;
            });

            self.updateTotalAmount();
        },

        /** Update total amount charged on card based on selected subscription
            charges. */
        updateTotalAmount: function() {
            var self = this;
            var candidates = self.element.find("input:radio");
            var totalAmountNode = self.element.find(".total-amount");
            var totalAmount = 0;
            for( var i = 0; i < candidates.length; ++i ) {
                var radio = $(candidates[i]);
                if( radio.is(':checked') ) {
                    totalAmount += parseInt(radio.val());
                }
            }
            candidates = self.element.find(".invoice-item td:nth-child(2)");
            for( var i = 0; i < candidates.length; ++i ) {
                var lineAmountText = $(candidates[i]).text();
                var first = lineAmountText.search('[0-9]');
                if( first > 0 ) {
                    var lineAmount = parseFloat(lineAmountText.substring(first)) * 100;
                    totalAmount += lineAmount;
                }
            }
            var totalAmountText = '' + (totalAmount / 100).toFixed(2);
            if( self.options.currency_unit == 'cad' ) {
                totalAmountText = '$' + totalAmountText + ' CAD';
            } else {
                totalAmountText = '$' + totalAmountText;
            }
            totalAmountNode.text(totalAmountText);
            if( totalAmount > 0 ) {
                if( !$("#card-use").is(':visible') ) $("#card-use").slideDown();
            } else {
                if( $("#card-use").is(':visible') ) $("#card-use").slideUp();
            }
        },
    }

    $.fn.invoice = function(options) {
        var opts = $.extend( {}, $.fn.invoice.defaults, options );
        invoice = new Invoice($(this), opts);
    };

    $.fn.invoice.defaults = {
        'currency_unit': 'usd',
        'saas_api_cart': '/api/cart/',
    };

   /* redeem a ``Coupon``. */
   function Redeem(el, options){
      this.element = $(el);
      this.options = options;
      this._init();
   }

   Redeem.prototype = {
      _init: function () {
          var self = this;
          this.element.submit(function() {
              var code = $(this).find('[name="code"]').val();
              self._redeem(code);
              // prevent the form from submitting with the default action
              return false;
          });
      },

      _redeem: function(code) {
          $.ajax({ type: "POST",
                   url: this.options.saas_api_redeem_coupon,
                   data: JSON.stringify({"code": code }),
                   dataType: "json",
                   contentType: "application/json; charset=utf-8",
                 }).done(function(data) {
                     // XXX does not show messages since we reload...
                     showMessages([data['details']]);
                     location.reload();
                 }).fail(function(data) {
                     if('details' in data.responseJSON) {
                         showMessages(
                             [data.responseJSON['details']], "danger");
                     } else {
                         showMessages(["Error " + data.status + ": "
+ data.responseText + ". Please accept our apologies."], "danger");
                     }
                 });
          return false;
      }
   }

   $.fn.redeem = function(options) {
      var opts = $.extend( {}, $.fn.redeem.defaults, options );
      redeem = new Redeem($(this), opts);
   };

   $.fn.redeem.defaults = {
       'saas_api_redeem_coupon': '/api/cart/redeem/',
   };

})(jQuery);
