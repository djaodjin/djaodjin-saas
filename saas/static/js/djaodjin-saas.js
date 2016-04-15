/* Functionality related to the SaaS API.
 */
/*global location setTimeout jQuery*/
/*global getMetaCSRFToken showMessages*/

function CartItem(options) {
    "use strict";
    this.item = {};
    var restricted = ["plan", "nb_periods", "first_name", "last_name", "email"];
    for(var i = 0; i < restricted.length; ++i ){
        var key = restricted[i];
        if( key in options ) {
            this.item[key] = options[key];
        }
    }
    this.urls = options.urls;
}


CartItem.prototype = {
    add: function(successFunc, errorFunc) {
        "use strict";
        var self = this;
        $.ajax({ type: "POST", // XXX Might still prefer to do PUT on list.
                 url: self.urls.saas_api_cart,
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                 },
                 data: JSON.stringify(self.item),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: successFunc,
                 error: errorFunc
               });
    },

    remove: function(successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "DELETE",
                 url: self.urls.saas_api_cart + self.item.plan + "/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                 },
                 success: successFunction
               });
    }
};

(function ($) {
    "use strict";

    /** Monitor the state (in-process, declined, etc.) of a ``Charge``

        HTML requirements:

        <... class="charge-status"
             data-charge-done="HTML to display when charge succeeded."
             data-charge-failed="HTML to display when charge failed."
             data-charge-disputed="HTML to display when charge was disputed."
             data-charge-created="HTML to display when charge is in progress.">
        </...>
     */
    function ChargeMonitor(el, options){
        this.element = $(el);
        this.options = options;
        this.init();
    }

    ChargeMonitor.prototype = {
        init: function () {
            var self = this;
            if( self.options.initialState === "created" ) {
                self.waitForCompletion();
            }
        },

        waitForCompletion: function() {
            var self = this;
            $.ajax({
                type: "GET",
                url: self.options.saas_api_charge,
                datatype: "json",
                contentType: "application/json; charset=utf-8",
                success: function(data) {
                    if( data.state === "created" ) {
                        setTimeout(function() {
                            self.waitForCompletion(); }, 1000);
                    } else {
                        var statusElement = self.element.find(".charge-status");
                        statusElement.text(
                            statusElement.attr("data-charge-" + data.state));
                    }
                }
            });
        }
    };

    $.fn.chargeMonitor = function(options) {
        var opts = $.extend( {}, $.fn.chargeMonitor.defaults, options );
        return new ChargeMonitor($(this), opts);
    };

    $.fn.chargeMonitor.defaults = {
        initialState: "created",
        saas_api_charge: null
    };

    /** Email a receipt for a charge. This behavior is typically associated
        to a button.
     */
    function ChargeEmailReceipt(el, options){
        this.element = $(el);
        this.options = options;
        this.init();
    }

    ChargeEmailReceipt.prototype = {
        init: function () {
            var self = this;
            self.state = self.options.initialState;
            self.element.click(function (event) {
                event.preventDefault();
                self.emailReceipt();
            });
        },

        emailReceipt: function() {
            var self = this;
            if( self.state === "created" ) {
                setTimeout(function() {
                    $.ajax({
                        type: "GET",
                        url: self.options.saas_api_charge,
                        datatype: "json",
                        contentType: "application/json; charset=utf-8",
                        success: function(data) {
                            self.state = data.state;
                            self.emailReceipt();
                        }
                    });
                }, 1000);
            } else {
                $.ajax({
                    type: "POST",
                    url: self.options.saas_api_email_charge_receipt,
                    beforeSend: function(xhr) {
                        xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                    },
                    datatype: "json",
                    contentType: "application/json; charset=utf-8",
                    success: function(data) {
                        showMessages(["A copy of the receipt was sent to " + data.email + "."], "info");
                    },
                    error: function(data) {
                        showMessages(["An error occurred while emailing a copy of the receipt (" + data.status + " " + data.statusText + "). Please accept our apologies."], "error");
                    }
                });
            }
        }
    };

    $.fn.chargeEmailReceipt = function(options) {
        var opts = $.extend( {}, $.fn.chargeEmailReceipt.defaults, options );
        return new ChargeEmailReceipt($(this), opts);
    };

    $.fn.chargeEmailReceipt.defaults = {
        initialState: "created",
        saas_api_email_charge_receipt: null
    };

    /** Decorate a form to create a refund on a ``ChargeItem``.

        HTML requirements:
        <form>
          <input name="amount">
          <button type="submit"></button>
        </form>
     */
    function Refund(el, options){
        this.element = $(el);
        this.options = options;
        this.init();
    }

    Refund.prototype = {
        init: function () {
            var self = this;
            var refundedInput = self.element.find("[name='amount']");
            var availableAmount =
                (self.options.availableAmount / 100).toFixed(2);
            refundedInput.attr("max", availableAmount);
            refundedInput.attr("data-linenum", self.options.linenum);
            refundedInput.val(availableAmount);
            var submitButton = self.element.find("[type='submit']");
            // Make sure we unbind the previous handler to avoid double submits
            submitButton.off("click");
            submitButton.click(function() {
                return self.submit();
            });
        },

        submit: function() {
            var self = this;
            var refundButton = self.options.refundButton;
            var refundedInput = self.element.find("[name='amount']");
            var availableAmount = refundedInput.attr("max");
            var linenum = refundedInput.attr("data-linenum");
            var refundedAmount = refundedInput.val();
            availableAmount = parseInt(
                parseFloat(availableAmount.replace(/[^\d\.]/g, "")) * 100);
            refundedAmount = parseInt(
                parseFloat(refundedAmount.replace(/[^\d\.]/g, "")) * 100);
            if( refundedAmount > availableAmount ) {
                refundedAmount = availableAmount;
            }
            if( refundedAmount > 0 ) {
                refundButton.attr("disabled", "disabled");
                $.ajax({
                    type: "POST",
                    url: self.options.saas_api_charge_refund,
                    beforeSend: function(xhr) {
                        xhr.setRequestHeader(
                            "X-CSRFToken", getMetaCSRFToken());
                    },
                    data: JSON.stringify({"lines":
                        [{"num": linenum, "refunded_amount": refundedAmount}]}),
                    datatype: "json",
                    contentType: "application/json; charset=utf-8",
                    success: function(data) {
                        var message = "Amount refunded.";
                        if( data.responseJSON ) {
                            message = data.responseJSON.detail;
                        }
                        showMessages([message], "info");
                        refundButton.replaceWith("<em>Refunded</em>");
                    },
                    error: function(data) {
                        var message = data.statusText;
                        if( data.responseJSON ) {
                            message = data.responseJSON.detail;
                        }
                        showMessages([
                         "An error occurred while refunding the charge ("
                         + data.status + " - " +
                         message + "). Please accept our apologies."], "error");
                        refundButton.removeAttr("disabled");
                    }
                });
            }
        }
    };

    $.fn.refund = function(options) {
        var opts = $.extend({}, $.fn.refund.defaults, options);
        return new Refund($(this), opts);
    };

    $.fn.refund.defaults = {
        availableAmount: 0,
        linenum: 0,
        saas_api_charge_refund: null,
        refundButton: null
    };

    /** Invoice
     */
    function Invoice(el, options){
        this.element = $(el);
        this.options = options;
        this.init();
    }

    Invoice.prototype = {
        init: function () {
            var self = this;

            self.element.find("input:radio").change(function() {
                self.updateTotalAmount();
            });

            self.element.find(".add-seat").click(function(event) {
                event.preventDefault();
                var subscription = $(this).parents("tbody");
                var prevLine = $(this).parents("tr").prev();
                var seatFirstName = subscription.find(".seat-first-name");
                var seatLastName = subscription.find(".seat-last-name");
                var seatEmail = subscription.find(".seat-email");
                var item = new CartItem({
                    plan: subscription.attr("data-plan"),
                    first_name: seatFirstName.val(),
                    last_name: seatLastName.val(),
                    email: seatEmail.val(),
                    urls: { saas_api_cart: self.options.saas_api_cart }});
                seatFirstName.val("");
                seatLastName.val("");
                seatEmail.val("");
                item.add(function(data, textStatus, jqXHR) {
                    var msg = data.first_name + " " + data.last_name +
                    " (" + data.email + ")";
                    var newLine = prevLine;
                    if( jqXHR.status === 201 ) {
                        newLine = prevLine.clone();
                        prevLine.removeClass("alert alert-info");
                        var clonedNode = $(newLine.children("td")[2]);
                        clonedNode.text(clonedNode.text().replace(
                                /, for .*/, ", for " + msg));
                        newLine.insertAfter(prevLine);
                    } else {
                        var descrNode = $(newLine.children("td")[2]);
                        descrNode.text(descrNode.text() + ", for " + msg);
                    }
                    newLine.addClass("alert alert-info");
                    self.updateTotalAmount();
                }, function(result) {
                    var msgs = [];
                    for( var field in result.responseJSON ) {
                        msgs = msgs.concat(result.responseJSON[field]);
                    }
                    if( (msgs.length <= 0) ) {
                        msgs = ["ERROR " + result.status + ": " + result.statusText];
                    }
                    showMessages(msgs, "error");
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
                if( radio.is(":checked") ) {
                    totalAmount += parseInt(radio.val());
                }
            }
            candidates = self.element.find(".invoice-item td:nth-child(2)");
            for( i = 0; i < candidates.length; ++i ) {
                var lineAmountText = $(candidates[i]).text().replace(',','');
                var first = lineAmountText.search("[0-9]");
                if( first > 0 ) {
                    var lineAmount = parseFloat(lineAmountText.substring(first)) * 100;
                    totalAmount += lineAmount;
                }
            }
            var grouped = "$";
            var totalAmountText = "" + (totalAmount / 100).toFixed(2);
            if( self.options.currency_unit === "cad" ) {
                grouped = "$";
            } else {
                totalAmountText = "$" + totalAmountText;
            }
            var grouped = "";
            var sep = "";
            for( var idx = totalAmountText.length - 3 ; idx > 3; idx -= 3 ) {
                grouped += totalAmountText.substring(idx - 3, idx) + sep;
                sep = ",";
            }
            grouped = (totalAmountText.substring(0, idx) + grouped
                       + totalAmountText.substring(totalAmountText.length - 3));
            if( self.options.currency_unit === "cad" ) {
                grouped = grouped + " CAD";
            }
            totalAmountNode.text(grouped);
            var cardUse = self.element.parents("form").find("#card-use");
            if( totalAmount > 0 ) {
                if( !cardUse.is(":visible") ) { cardUse.slideDown(); }
            } else {
                if( cardUse.is(":visible") ) { cardUse.slideUp(); }
            }
        }
    };

    $.fn.invoice = function(options) {
        var opts = $.extend( {}, $.fn.invoice.defaults, options );
        return new Invoice($(this), opts);
    };

    $.fn.invoice.defaults = {
        currency_unit: "usd",
        saas_api_cart: "/api/cart/"
    };

   /* redeem a ``Coupon``. */
   function Redeem(el, options){
      this.element = $(el);
      this.options = options;
      this.init();
   }

   Redeem.prototype = {
      init: function () {
          var self = this;
          this.element.submit(function() {
              var code = $(this).find("[name='code']").val();
              self.redeemCode(code);
              // prevent the form from submitting with the default action
              return false;
          });
      },

      redeemCode: function(code) {
          $.ajax({ type: "POST",
                   url: this.options.saas_api_redeem_coupon,
                   beforeSend: function(xhr) {
                       xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                   },
                   data: JSON.stringify({"code": code }),
                   dataType: "json",
                   contentType: "application/json; charset=utf-8"
                 }).done(function(data) {
                     // XXX does not show messages since we reload...
                     showMessages([data.details], "success");
                     location.reload();
                 }).fail(function(data) {
                     if("details" in data.responseJSON) {
                          showMessages(
                            [data.responseJSON.details], "error");
                     } else {
                          showMessages(["Error " + data.status + ": " +
                            data.responseText + ". Please accept our apologies."], "error");
                     }
                 });
          return false;
      }
   };

   $.fn.redeem = function(options) {
      var opts = $.extend( {}, $.fn.redeem.defaults, options );
      return new Redeem($(this), opts);
   };

   $.fn.redeem.defaults = {
       saas_api_redeem_coupon: "/api/cart/redeem/"
   };

   /** Decorate an HTML controller to delete ``Organization``s.
    */
   function Profile(el, options){
      this.element = $(el);
      this.options = options;
      this.init();
   }

   Profile.prototype = {
      init: function () {
          var self = this;
          this.element.click(function() {
              self.deleteProfile();
              // prevent the form from submitting with the default action
              return false;
          });
      },

      deleteProfile: function() {
          var self = this;
          $.ajax({ type: "DELETE",
                 url: self.options.saas_api_organization,
                 dataType: "json",
                 contentType: "application/json; charset=utf-8",
          }).done(function(data) {
            /* When we DELETE the request.user profile, it will lead
               to a logout. When we delete a different profile, a reload
               of the page leads to a 404. In either cases, moving on
               to the redirect_to_profile page is a safe bet. */
            window.location = self.options.user_profile_redirect;
          }).fail(function(data) {
            if('details' in data.responseJSON) {
                showMessages([data.responseJSON['details']], "error");
            } else {
                showMessages(["Error " + data.status + ": "
+ data.responseText + ". Please accept our apologies."], "error");
            }
          });
      }
   };

   $.fn.profile = function(options) {
      var opts = $.extend( {}, $.fn.profile.defaults, options );
      return new Profile($(this), opts);
   };

   $.fn.profile.defaults = {
       saas_api_organization: "/api/profile",
       user_profile_redirect: "/users/"
   };

   /** Decorate an HTML controller to trigger AJAX requests to create,
       activate and delete ``Plan``s.

       HTML requirements:

       <div data-plan="_plan-slug_">
         <button class="activate"></button>
         <button class="delete"></button>
       </div>
    */
   function Plan(el, options){
      this.element = $(el);
      this.options = options;
      this.init();
   }

   Plan.prototype = {
      init: function () {
          var self = this;
          self.id = self.element.attr("data-plan");
          self.element.find(".activate").click(function() {
              self.toggleActivatePlan();
              // prevent the form from submitting with the default action
              return false;
          });
          var deleteBtn = self.element.find(".delete");
          if( deleteBtn ) {
              var target = deleteBtn.data("target");
              if( target !== undefined ) {
                  deleteBtn = $(target).find(".delete");
              }
          }
          deleteBtn.click(function() {
              self.destroy();
          });
      },

      create: function(reload) {
        "use strict";
        var self = this;
        $.ajax({ type: "POST",
                 url: self.options.saas_api_plan + "/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                 },
                 data: JSON.stringify({
                     "title": "New Plan",
                     "description": "Write the description of the plan here.",
                     "interval": 4,
                     "is_active": 1}),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: function(data) {
                     showMessages([
                         "Plan was created successfully."], "success");
                     if( reload ) { location.reload(true); }
                 },
                 error: function(data) {
                     showMessages([
                         "An error occurred while creating the plan (" +
                         data.status + " " + data.statusText +
                         "). Please accept our apologies."], "error");
                 }
               });
      },

      /** Update fields in a ``Plan`` by executing an AJAX request
          to the service. */
      update: function(data, successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "PUT",
                 url: self.options.saas_api_plan + "/" + self.id + "/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                 },
                 async: false,
                 data: JSON.stringify(data),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: successFunction
               });
      },

      destroy: function() {
        "use strict";
        var self = this;
        $.ajax({ type: "DELETE",
                 url: self.options.saas_api_plan + "/" + self.id + "/",
                 async: false,
                 success: function(data) {
                     window.location.href = self.options.saas_metrics_plans;
                     showMessages([
                         "Plan was successfully deleted."], "success");
                 },
                 error: function(data) {
                     showMessages([
                         "An error occurred while deleting the plan (" +
                         data.status + " " + data.statusText +
                         "). Please accept our apologies."], "error");
                 }
               });
      },

      get: function(successFunction) {
        "use strict";
        var self = this;
        $.ajax({ type: "GET",
                 url: self.options.saas_api_plan + "/" + self.id + "/",
                 success: successFunction
               });
      },

      /** Toggle a ``Plan`` from active to inactive and vise-versa
          by executing an AJAX request to the service. */
      toggleActivatePlan: function() {
          "use strict";
          var self = this;
          var button = self.element.find(".activate");
          $.ajax({type: "PUT",
                 url: self.options.saas_api_plan + "/" + self.id + "/activate/",
                 beforeSend: function(xhr) {
                     xhr.setRequestHeader("X-CSRFToken", getMetaCSRFToken());
                 },
                 data: JSON.stringify({
                     "is_active": !button.hasClass("activated")}),
                 datatype: "json",
                 contentType: "application/json; charset=utf-8",
                 success: function(data) {
                     if( data.is_active ) {
                         button.addClass("activated");
                         button.text("Deactivate");
                     } else {
                         button.removeClass("activated");
                         button.text("Activate");
                     }
                 },
                 error: function(data) {
                     showMessages([
                         "An error occurred while creating the plan (" +
                         data.status + " " + data.statusText +
                         "). Please accept our apologies."], "error");
                 },
          });
      }
   };

   $.fn.plan = function(options) {
      var opts = $.extend( {}, $.fn.plan.defaults, options );
      return new Plan($(this), opts);
   };

   $.fn.plan.defaults = {
       saas_api_plan: "/api/plan",
       saas_metrics_plans: "/plan"
   };

})(jQuery);
