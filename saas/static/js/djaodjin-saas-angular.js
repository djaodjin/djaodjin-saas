/*=============================================================================
  Apps
  ============================================================================*/

var saasApp = angular.module("saasApp", [
    "ui.bootstrap", "ngDragDrop", "ngRoute",
    "balanceControllers", "balanceServices",
    "metricsControllers", "importTransactionsControllers",
    "transactionControllers", "profileControllers", "saasFilters"]);

/*=============================================================================
  Filters
  ============================================================================*/
angular.module("saasFilters", [])
    .filter('unsafe', function($sce) {
      return function(val) {
        return $sce.trustAsHtml(val);
      };
    }).filter("monthHeading", function() {
        "use strict";
        return function(d) {
            // shift each period by 1 month unless this is
            // current month and not a first day of the month
            if( typeof d === 'string' ) {
                d = moment(d);
            }
            if(d.date() !== 1 || d.hour() !== 0
               || d.minute() !== 0 || d.second() !== 0 ) {
                return d.format("MMM'YY*");
            }
            return d.clone().subtract(1, 'months').format("MMM'YY");
        };
    })
    .filter("currencyToSymbol", function() {
        "use strict";
        return function(currency) {
            if( currency === "usd" || currency === "cad" ) { return "$"; }
            else if( currency === "eur" ) { return "\u20ac"; }
            return currency;
        };
    })
    .filter('formatDate', function() {
        return function(at_time, format) {
            if (at_time) {
                if(!format){
                    //format = 'MM/DD/YYYY hh:mm'
                    format = "MMM D, YYYY";
                }
                if(!(at_time instanceof Date)){
                    at_time = String(at_time);
                }
                return moment(at_time).format(format)
            }
        };
    })
    .filter("humanizeCell", function(currencyFilter, numberFilter, currencyToSymbolFilter) {
        "use strict";
        return function(cell, unit, scale, abbreviate) {
            if(typeof abbreviate === "undefined"){
                abbreviate = true;
            }
            scale = scale || 1;
            var value = cell * scale;
            if(unit) {
                var symbol = currencyToSymbolFilter(unit);
                return currencyFilter(value, symbol, 2);
            }
            return numberFilter(value);
        };
    }).filter('groupBy', ['$parse', function ($parse) {
      //http://stackoverflow.com/questions/19992090/angularjs-group-by-directive
        return function (list, group_by) {
            var filtered = [];
            var prev_item = null;
            var group_changed = false;
            // this is a new field which is added to each item where we append
            // "_CHANGED" to indicate a field change in the list
            // force group_by into Array
            group_by = angular.isArray(group_by) ? group_by : [group_by];

            var new_field = group_by.join('_').replace('.', '_') + '_CHANGED';

            // loop through each item in the list
            angular.forEach(list, function (item) {
                group_changed = false;
                // if not the first item
                if (prev_item !== null) {
                    // check if any of the group by field changed
                    //check each group by parameter
                    for (var i = 0, len = group_by.length; i < len; i++) {
                        if ($parse(group_by[i])(prev_item) !== $parse(group_by[i])(item)) {
                            group_changed = true;
                        }
                    }
                }// otherwise we have the first item in the list which is new
                else {
                    group_changed = true;
                }

                // if the group changed, then add a new field to the item
                // to indicate this
                if (group_changed) {
                    item[new_field] = true;
                } else {
                    item[new_field] = false;
                }

                filtered.push(item);
                prev_item = item;
            });
            return filtered;
        };
    }]).filter('relativeDate', ["settings", function(settings) {
        // Generate a relative date for an instance with a ``created_at`` field.
        return function(at_time) {
            var cutOff = new Date();
            if( settings.date_range && settings.date_range.ends_at ) {
                cutOff = new Date(settings.date_range.ends_at);
            }
            var dateTime = new Date(at_time);
            if( dateTime <= cutOff ) {
                return moment.duration(cutOff - dateTime).humanize() + " ago";
            } else {
                return moment.duration(dateTime - cutOff).humanize() + " left";
            }
        };
    }]);

//=============================================================================
// Controllers
//============================================================================

var transactionControllers = angular.module("transactionControllers", []);
var metricsControllers = angular.module("metricsControllers", []);
var importTransactionsControllers = angular.module("importTransactionsControllers", []);
var profileControllers = angular.module("profileControllers", []);


transactionControllers.controller("itemsListCtrl",
    ["$scope", "$http", "$timeout", "$filter", "settings",
     function($scope, $http, $timeout, $filter, settings) {
    "use strict";
    $scope.items = {};
    $scope.totalItems = 0;

    $scope.humanizeTotal = function() {
        return $filter('humanizeCell')($scope.items.total, $scope.items.unit, 0.01);
    }

    $scope.humanizeBalance = function() {
        return $filter('humanizeCell')($scope.items.balance, $scope.items.unit, 0.01);
    }

    $scope.setDataRange = function(params, start_at, ends_at) {
        if( start_at ) {
            params['start_at'] = moment(start_at).toDate();
        }
        if( ends_at ) {
            params['ends_at'] = moment(ends_at).toDate()
        }
        return params;
    }

    $scope.resetDefaults = function(overrides) {
        var opts = {q: ""};
        if( settings.sortByField ) {
            opts['o'] = settings.sortByField;
            opts['ot'] = settings.sortDirection || "desc";
        }
        if( settings.date_range ) {
            $scope.setDataRange(opts,
                settings.date_range.start_at, settings.date_range.ends_at);
        }
        $scope.itemsPerPage = settings.itemsPerPage; // Must match server-side
        $scope.maxSize = 5;               // Total number of direct pages link
        $scope.currentPage = 1;
        // currentPage will be saturated at maxSize when maxSize is defined.
        $scope.formats = ["MMM dd, yyyy", "yyyy/MM/dd"];
        $scope.format = $scope.formats[0];
        $scope.opened = { "start_at": false, "ends_at": false };
        if( typeof overrides === "undefined" ) {
            overrides = {};
        }
        $scope.params = angular.merge({}, opts, overrides);
    };

    $scope.resetDefaults();

    // calendar for start_at and ends_at
    $scope.open = function($event, date_at) {
        $event.preventDefault();
        $event.stopPropagation();
        if( date_at === "start_at" || date_at === "ends_at") {
            $scope.opened[date_at] = true;
        } else {
            date_at.opened = true;
        }
    };

    $scope.$watch("params", function(newVal, oldVal, scope) {
        var updated = (newVal.o !== oldVal.o || newVal.ot !== oldVal.ot
            || newVal.q !== oldVal.q || newVal.page !== oldVal.page );
        if( (typeof newVal.start_at !== "undefined")
            && (typeof newVal.ends_at !== "undefined")
            && (typeof oldVal.start_at !== "undefined")
            && (typeof oldVal.ends_at !== "undefined") ) {
            /* Implementation Note:
               The Date objects can be compared using the >, <, <=
               or >= operators. The ==, !=, ===, and !== operators require
               you to use date.getTime(). Don't ask. */
            if( newVal.start_at.getTime() !== oldVal.start_at.getTime()
                && newVal.ends_at.getTime() === oldVal.ends_at.getTime() ) {
                updated = true;
                if( $scope.params.ends_at < newVal.start_at ) {
                    $scope.params.ends_at = newVal.start_at;
                }
            } else if( newVal.start_at.getTime() === oldVal.start_at.getTime()
                       && newVal.ends_at.getTime() !== oldVal.ends_at.getTime() ) {
                updated = true;
                if( $scope.params.start_at > newVal.ends_at ) {
                    $scope.params.start_at = newVal.ends_at;
                }
            }
        }

        if( updated ) {
            $scope.refresh();
        }
    }, true);

    $scope.filterList = function(regex) {
        if( regex ) {
            if ("page" in $scope.params){
                delete $scope.params.page;
            }
            $scope.params.q = regex;
        } else {
            delete $scope.params.q;
        }
    };

    $scope.getQueryString = function(excludes){
        var sep = "";
        var result = "";
        for( var key in $scope.params ) {
            if( $scope.params.hasOwnProperty(key) && $scope.params[key] ) {
                if( excludes && key in excludes ) continue;
                if( key === 'start_at' || key === 'ends_at' ) {
                    result += sep + key + '=' + moment(
                        $scope.params[key], $scope.format).toISOString();
                } else {
                    result += sep + key + '=' + $scope.params[key];
                }
                sep = "&";
            }
        }
        if( result ) {
            result = '?' + result;
        }
        return result;
    };

    $scope.pageChanged = function() {
        if( $scope.currentPage > 1 ) {
            $scope.params.page = $scope.currentPage;
        } else {
            delete $scope.params.page;
        }
    };

    $scope.sortBy = function(fieldName) {
        if( $scope.params.o === fieldName ) {
            if( $scope.params.ot == "asc" ) {
                $scope.params.ot = "desc";
            } else {
                $scope.params.ot = "asc";
            }
        } else {
            // sorting by new field.
            $scope.params.ot = "asc";
        }
        $scope.params.o = fieldName;
        $scope.currentPage = 1;
        // pageChanged only called on click?
        delete $scope.params.page;
    };

    $scope.refresh = function() {
        $http.get(settings.urls.api_items,
            {params: $scope.params}).then(
            function(resp) {
                // We cannot watch items.count otherwise things start
                // to snowball. We must update totalItems only when it truly
                // changed.
                if( resp.data.count != $scope.totalItems ) {
                    $scope.totalItems = resp.data.count;
                }
                $scope.setDataRange($scope.params,
                    resp.data.start_at, resp.data.ends_at);
                $scope.items = resp.data;
                $scope.items.$resolved = true;
            }, function(resp) {
                $scope.items = {};
                $scope.items.$resolved = false;
                showErrorMessages(resp);
                $http.get(settings.urls.api_items,
                    {params: angular.merge({force: 1}, $scope.params)}).then(
                function success(resp) {
                    // ``force`` load will not call the processor backend
                    // for reconciliation.
                    if( resp.data.count != $scope.totalItems ) {
                        $scope.totalItems = resp.data.count;
                    }
                    $scope.items = resp.data;
                    $scope.items.$resolved = true;
                });
            });
    };

    if( settings.autoload ) {
        $scope.refresh();
    }
}]);


transactionControllers.controller("relationListCtrl",
    ["$scope", "$element", "$controller", "$http", "$timeout", "settings",
    function($scope, $element, $controller, $http, $timeout, settings) {
    "use strict";
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout, settings: settings});

    $scope.unregistered = null;

    $scope.getCandidates = function(val) {
        if( typeof settings.urls.api_candidates === "undefined" ) {
            return [];
        }
        return $http.get(settings.urls.api_candidates, {
            params: {q: val}
        }).then(function(res){
            return res.data.results;
        });
    };

    $scope.create = function($event) {
        $event.preventDefault();
        var dialog = $element.find(settings.modalSelector);
        if( dialog ) {
            if( dialog.data('bs.modal') ) {
                dialog.modal("hide");
            }
        }
        var emailField = dialog.find("[name='email']");
        if( emailField.val() === "" ) {
            var emailFieldGroup = emailField.parents(".form-group");
            var helpBlock = emailFieldGroup.find(".help-block");
            if( helpBlock.length === 0 ) {
                emailField.parent().append("<span class=\"help-block\">This field cannot be empty.</span>");
            }
            emailFieldGroup.addClass("has-error");
            return;
        }
        if( !$scope.unregistered ) {
            $scope.unregistered = {};
        }
        if( !$scope.unregistered.hasOwnProperty('email')
              || typeof $scope.unregistered.email === "undefined" ) {
            $scope.unregistered.email = emailField.val();
        }
        $scope.unregistered.message = dialog.find("[name='message']").val();
        $http.post(settings.urls.api_items + "?force=1", $scope.unregistered).then(
            function success(resp) {
                // XXX Couldn't figure out how to get the status code
                //   here so we just reload the list.
                $scope.refresh();
                $scope.unregistered = null;
            },
            function error(resp) {
                showErrorMessages(resp);
            });
    };

    $scope.save = function($event, item) {
        $event.preventDefault();
        if( typeof item !== "undefined" ) {
            $scope.unregistered = item;
        }
        $http.post(settings.urls.api_items, $scope.unregistered).then(
            function(success) {
                // XXX Couldn't figure out how to get the status code
                // here so we just reload the list.
                $scope.refresh();
                $scope.unregistered = null;
            },
            function(resp) {
                if( resp.status === 404 ) {
                    // XXX hack to set full_name when org does not exist.
                    $scope.unregistered.full_name = $scope.unregistered.slug;
                    // XXX hack to set email when user does not exist.
                    $scope.unregistered.email = $scope.unregistered.slug;
                    var dialog = $element.find(settings.modalSelector);
                    if( dialog && jQuery().modal ) {
                        dialog.modal("show");
                    }
                } else {
                    showErrorMessages(resp);
                }
            });
    };

    $scope.remove = function ($event, idx) {
        $event.preventDefault();
        var slug = $($event.target).parents("[id]").attr("id");
        if( settings.user
            && $scope.items.results[idx].user
            && $scope.items.results[idx].user.slug === settings.user.slug ) {
            if( !confirm("You are about to delete yourself from this" +
                         " role. it's possible that you no longer can manage" +
                         " this organization after performing this " +
                         " action.\n\nDo you want to remove yourself " +
                         " from this organization?") ) {
                return;
            }
        }
        $http.delete(settings.urls.api_items + '/' + encodeURIComponent(slug)).then(
            function success(resp) {
                $scope.items.results.splice(idx, 1);
            },
            function error(resp) {
                showErrorMessages(resp);
            });
    };

}]);


transactionControllers.controller("CouponListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
     function($scope, $controller, $http, $timeout, settings) {
    "use strict";
    var opts = angular.merge({
        autoload: true,
        sortByField: "code",
        sortDirection: "asc",
        urls: {api_items: settings.urls.provider.api_coupons}},
        settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout: $timeout,
        settings: opts});

    $scope.newCoupon = {code: "", percent: ""};

    // calendar for expiration date
    $scope.open = function($event, coupon) {
        $event.preventDefault();
        $event.stopPropagation();
        coupon.opened = true;
    };

    $scope.getCouponApi = function(coupon) {
        return settings.urls.provider.api_coupons + '/' + coupon.code + '/';
    };

    $scope.getCouponUrl = function(coupon) {
        return settings.urls.provider.metrics_coupons + coupon.code + '/';
    };

    $scope.remove = function (idx) {
        $http.delete($scope.getCouponApi($scope.items.results[idx])).then(
        function success(resp) {
            $scope.refresh();
        });
    };

    $scope.save = function() {
        $http.post(settings.urls.provider.api_coupons, $scope.newCoupon).then(
        function success(resp) {
            $scope.items.results.push(resp.data);
            // Reset our editor to a new blank post
            $scope.newCoupon = {code: "", percent: ""};
        }, function error(resp){
            showErrorMessages(resp);
        });
    };

    $scope.$watch("items", function(newVal, oldVal, scope) {
        if( newVal.hasOwnProperty("results") &&
            oldVal.hasOwnProperty("results") ) {
            var length = ( oldVal.results.length < newVal.results.length ) ?
                oldVal.results.length : newVal.results.length;
            for( var i = 0; i < length; ++i ) {
                if( oldVal.results[i].code == newVal.results[i].code &&
                    ((oldVal.results[i].ends_at !== newVal.results[i].ends_at)
                    || (oldVal.results[i].description !== newVal.results[i].description)) ) {
                    $http.put($scope.getCouponApi(newVal.results[i]), newVal.results[i]).then(
                    function success() {
                        // XXX We don't show messages here because it becomes
                        // quickly annoying if they do not disappear
                        // automatically.
                        // showMessages(["Coupon was successfully updated."], "success");
                    });
                }
            }
        }
    }, true);

    $scope.editDescription = function (idx){
        $scope.edit_description = Array.apply(
            null, new Array($scope.items.results.length)).map(function() {
            return false;
        });
        $scope.edit_description[idx] = true;
        $timeout(function(){
            angular.element("#input_description").focus();
        }, 100);
    };

    $scope.saveDescription = function(event, coupon, idx){
        if (event.which === 13 || event.type === "blur" ){
            $scope.edit_description[idx] = false;
        }
    };
}]);


transactionControllers.controller("userRelationListCtrl",
    ["$scope", "$element", "$attrs", "$controller",
     "$http", "$timeout", "settings",
    function($scope, $element, $attrs, $controller, $http, $timeout, settings) {
    "use strict";
    var apiUrl = ($attrs.apiUrl && $scope.roleDescription
                  && $scope.roleDescription.slug) ?
        ($attrs.apiUrl + '/' + $scope.roleDescription.slug)
        : settings.urls.organization.api_roles;
    var opts = angular.merge({
        autoload: true,
        sortByField: "username",
        sortDirection: "desc",
        modalSelector: ".add-role-modal",
        urls: {api_items: apiUrl,
               api_candidates: settings.urls.api_candidates}}, settings);
    $controller("relationListCtrl", {
        $scope: $scope, $element: $element, $controller: $controller,
        $http: $http, $timeout:$timeout, settings: opts});
}]);


transactionControllers.controller("userRoleDescriptionCtrl",
    ["$scope", "$controller", "$http", "$timeout", "$attrs", "settings",
    function($scope, $controller, $http, $timeout, $attrs, settings) {
    "use strict";

    $scope.newRoleDescription = null;
    $scope.newRole = null;
    $scope.selectedRoleDescription = null;
    $scope.organization = $attrs.saasOrganization;

    var opts = angular.merge({
        autoload: true,
        urls: {api_items: settings.urls.organization.api_role_descriptions}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout: $timeout,
        settings: opts});

    $scope.addRoleDescription = function() {
        $scope.newRoleDescription = null;
        var dialog = angular.element("#new-role-description");
    };

    $scope.createRoleDescription = function() {
        $http.post(settings.urls.organization.api_role_descriptions,
                   $scope.newRoleDescription).then(function() {
            var dialog = angular.element("#new-role-description");
            if (dialog.data("bs.modal")) {
                dialog.modal("hide");
            }
            $scope.refresh();
        });
    };

    $scope.deleteRoleDescription = function(roleDescription) {
        var url = settings.urls.organization.api_role_descriptions +
                  "/" + roleDescription.slug;

        $http.delete(url).then(function() {
            $scope.refresh();
        });
    }
}]);


// XXX Currently most of the functionality of subscriberListCtrl is actually
// included here.
transactionControllers.controller("subscriptionListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    "use strict";

    var opts = angular.merge({
        sortByField: "created_at",
        sortDirection: "desc",
        date_range: {ends_at: moment().endOf("day").toDate()}}, settings);

    $controller('itemsListCtrl', {
        $scope: $scope, $controller: $controller, $http: $http,
        $timeout:$timeout, settings: opts});

    $scope.tables = {
        registered: {
            $resolved: false, count: 0,
            location: ((settings.urls.broker
              && settings.urls.broker.api_users_registered) ?
                settings.urls.broker.api_users_registered : null)},
        subscribed: {
            $resolved: false, count: 0,
            location: settings.urls.organization.api_subscriptions},
        churned: {
            $resolved: false, count: 0,
            location: ((settings.urls.provider
              && settings.urls.provider.api_subscribers_churned) ?
                settings.urls.provider.api_subscribers_churned : null)}
    };

    $scope.active = $scope.tables.subscribed;

    $scope.query = function(queryset) {
        queryset.$resolved = false;
        queryset.results = [];
        if( queryset.location ) {
            $http.get(queryset.location, {params: $scope.params}).then(
            function success(resp) {
                queryset.results = resp.data.results;
                queryset.count = resp.data.count;
                queryset.$resolved = true;
            });
        }
    };

    $scope.refresh = function() {
        $scope.query($scope.active);
        for( var table in $scope.tables ) {
            if( $scope.tables.hasOwnProperty(table)
                && $scope.tables[table] !=  $scope.active ) {
                $scope.query($scope.tables[table]);
            }
        }
    };

    $scope.subscribersURL = function(provider, plan) {
        return settings.urls.organization.api_profile_base + provider + "/plans/" + plan + "/subscriptions/";
    };

    $scope.subscriptionURL = function(organization, plan) {
        return settings.urls.organization.api_profile_base
            + organization + "/subscriptions/" + plan;
    };

    // Returns ends-soon when the subscription is about to end.
    $scope.endsSoon = function(subscription) {
        var cutOff = new Date($scope.params.ends_at);
        cutOff.setDate($scope.params.ends_at + 5);
        var subEndsAt = new Date(subscription.ends_at);
        if( subEndsAt < cutOff ) {
            return "ends-soon";
        }
        return "";
    };

    $scope.editDescription = function (event, entry) {
        var input = angular.element(event.target).parent().find("input");
        entry.editDescription = true;
        $timeout(function() {
            input.focus();
        }, 100);
    };

    $scope.saveDescription = function(event, entry){
        if (event.which === 13 || event.type === "blur" ){
            delete entry.editDescription;
            $http.patch($scope.subscriptionURL(
                entry.organization.slug, entry.plan.slug),
                {description: entry.description}).then(
                function(data){
                    // XXX message expiration date was updated.
            });
        }
    };

    $scope.$watch("tables.subscribed", function(newVal, oldVal, scope) {
        if( newVal.hasOwnProperty("results") &&
            oldVal.hasOwnProperty("results") ) {
            var length = ( oldVal.results.length < newVal.results.length ) ?
                oldVal.results.length : newVal.results.length;
            for( var i = 0; i < length; ++i ) {
                if( (oldVal.results[i].ends_at !== newVal.results[i].ends_at)
                    || (oldVal.results[i].description !== newVal.results[i].description)) {
                    var entry = newVal.results[i];
                    $http.patch($scope.subscriptionURL(
                        entry.organization.slug, entry.plan.slug),
                        {ends_at: entry.ends_at,
                         description: entry.description}).then(
                        function(data){
                            // We don't show messages here because it becomes
                            // quickly annoying if they do not disappear
                            // automatically.
                        }, function(resp) {
                            showErrorMessages(resp);
                        });
                }
            }
        }
    }, true);

    // Change the active tab.
    // XXX We need this method because filters are "global" accross all tabs.
    $scope.tabClicked = function($event) {
        var newActiveTab = $event.target.getAttribute("href").replace(/^#/, "");
        for( var table in $scope.tables ) {
            if( $scope.tables.hasOwnProperty(table)
                && newActiveTab === table ) {
                $scope.active = $scope.tables[table];
            }
        }
    };

    $scope.plan = "{}"; // plan to subscribe to.

    $scope.subscribe = function(organization) {
        var plan = JSON.parse($scope.plan);
        $http.post($scope.subscribersURL(plan.organization, plan.slug), {
            organization: {
              slug: organization
            }
        }).then(
        function success(resp) {
            $scope.refresh();
        }, function error(resp) {
            showErrorMessages(resp);
        });
        // prevent the form from submitting with the default action
        return false;
    };

    $scope.acceptRequest = function(organization, request_key) {
        $http.post(settings.urls.organization.api_profile_base
            + organization + "/subscribers/accept/" + request_key + "/").then(
        function success(resp) {
            $scope.refresh();
        }, function error(resp) {
            showErrorMessages(resp);
        });
    };

    $scope.unsubscribe = function(organization, plan, target) {
        var dialog = angular.element(target + " [type=\"submit\"]");
        dialog.attr("data-organization", organization);
        dialog.attr("data-plan", plan);
    };

    $scope.unsubscribeConfirmed = function(event) {
        var elm = angular.element(event.target);
        var organization = elm.attr("data-organization");
        var plan = elm.attr("data-plan");
        $http.delete($scope.subscriptionURL(organization, plan)).then(
        function success(resp) {
            $scope.refresh();
        }, function error(resp) {
            showErrorMessages(resp);
        });
    };
}]);


transactionControllers.controller("subscriberListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    settings.urls.organization.api_subscriptions = settings.urls.provider.api_subscribers_active;
    $controller('subscriptionListCtrl', {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: settings});
}]);


transactionControllers.controller("planSubscribersListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    "use strict";
    $controller('subscriptionListCtrl', {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: settings});

    $scope.subscribers = {
        $resolved: false, count: 0,
        location: settings.urls.provider.api_plan_subscribers};

    $scope.active = $scope.subscribers;

    $scope.refresh = function() {
      $scope.query($scope.subscribers);
    };
}]);


transactionControllers.controller("transactionListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    var opts = angular.merge({
        autoload: true,
        sortByField: "created_at",
        sortDirection: "desc",
        urls: {api_items: settings.urls.organization.api_transactions}},
        settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: opts});
}]);


transactionControllers.controller("billingStatementCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    $scope.cancelBalance = function($event) {
        $event.preventDefault();
        $http.delete(settings.urls.organization.api_cancel_balance_due).then(
            function success(resp) {
                $scope.resetDefaults();
                if( $scope.params.ends_at ) {
                    delete $scope.params['ends_at'];
                }
                $scope.refresh();
            },
            function error(resp) {
                showErrorMessages(resp);
            });
        return 0;
    };

    $controller("transactionListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: settings});
}]);


transactionControllers.controller("billingSummaryCtrl",
    ["$scope", "$attrs", "$controller", "$http", "$timeout", "$filter", "settings",
    function($scope, $attrs, $controller, $http, $timeout, $filter, settings) {
    "use strict";
    var apiUrl = $attrs.apiUrl ? $attrs.apiUrl : settings.urls.provider.api_bank;

    $scope.last4 = "N/A";
    $scope.exp_date = "N/A";
    $scope.bank_name = "N/A";
    $scope.balance_amount = "N/A";
    $scope.balance_unit = "N/A";

    $scope.humanizeBalance = function() {
        return $filter('humanizeCell')($scope.balance_amount, $scope.balance_unit, 0.01);
    }

    if( apiUrl ) {
        $http.get(apiUrl).then(
        function success(resp) {
            $scope.balance_amount = resp.data.balance_amount;
            $scope.balance_unit = resp.data.balance_unit;
            if( resp.data.last4 ) {
                $scope.last4 = resp.data.last4;
            }
            if( resp.data.exp_date ) {
                $scope.exp_date = resp.data.exp_date;
            }
            $scope.bank_name = resp.data.bank_name;
            $scope.$resolved = true;
        });
    }
}]);


transactionControllers.controller("chargeListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    var opts = angular.merge({
        autoload: true,
        sortByField: "created_at",
        sortDirection: "desc",
        urls: {api_items: settings.urls.broker.api_charges}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: opts});
}]);


metricsControllers.controller("metricsCtrl",
    ["$scope", "$http", "$filter", "settings",
    function($scope, $http, $filter, settings) {
    "use strict";

    $scope.tables = settings.tables;
    $scope.tabs = [];
    for( var i = 0; i < $scope.tables.length; ++i ) {
        $scope.tabs.push($scope.tables[i].key);
    }
    $scope.currentTableData = $scope.tables[0];

    $scope.endOfMonth = function(date) {
        return new Date(
            date.getFullYear(),
            date.getMonth() + 1,
            0
        );
    };

    $scope.ends_at = moment().toDate();
    if( settings.date_range && settings.date_range.ends_at ) {
        $scope.ends_at = moment(settings.date_range.ends_at);
        if( $scope.ends_at.isValid() ) {
            $scope.ends_at = $scope.ends_at.toDate();
        }
    }
    $scope.period = 'monthly';

    // these aren't documented; do they do anything?
    $scope.formats = ["MMM dd, yyyy", "yyyy/MM/dd"];
    $scope.format = $scope.formats[0];
    $scope.dateOptions = {
        formatYear: "yyyy",
        startingDay: 1,
        mode: "month",
        minMode: "month"
    };
    $scope.opened = false;
    $scope.timezone = 'local';

    function convertDatetime(data, isUTC){
        // Convert datetime string to moment object in-place because we want
        // to keep extra keys and structure in the JSON returned by the API.
        return data.map(function(f){
            var values = f.values.map(function(v){
                // localizing the period to local browser time
                // unless showing reports in UTC.
                v[0] = isUTC ? moment.parseZone(v[0]) : moment(v[0]);
            });
        });
    }

    $scope.humanizeCell = function(value, unit, scale) {
        return $filter('humanizeCell')(value, unit, scale);
    };

    $scope.tabTitle = function(table) {
        var result = table.title;
        if( table.unit ) {
            result += "("+ $filter('currencyToSymbol')(table.unit) + ")";
        }
        return result;
    }

    $scope.prefetch = function() {
        for( var i = 0; i < $scope.tables.length; ++i ) {
            $scope.query($scope.tables[i]);
        }
    };

    $scope.query = function(queryset) {
        var params = {
            "ends_at": moment($scope.ends_at).format(),
            "period": $scope.period,
        };
        if( $scope.timezone !== 'utc' ) {
            params["timezone"] = moment.tz.guess();
        }
        $http.get(queryset.location, {params: params}).then(
        function success(resp) {
            var unit = resp.data.unit;
            var scale = resp.data.scale;
            scale = parseFloat(scale);
            if( isNaN(scale) ) {
                scale = 1.0;
            }
            // add "extra" rows at the end
            var extra = resp.data.extra || [];

            queryset.unit = unit;
            queryset.scale = scale;
            queryset.data = resp.data.table;
            convertDatetime(queryset.data, $scope.timezone === 'utc');
            // manual binding - trigger updates to the graph
            if( queryset.key === "balances") {
                // XXX Hard-coded.
                updateBarChart("#" + queryset.key +  " .chart-content",
                    queryset.data, unit, scale, extra);
            } else {
                updateChart("#" + queryset.key +  " .chart-content",
                    queryset.data, unit, scale, extra);
            }
        });
    };

    $scope.prepareCurrentTabData = function(ends_at, timezone, period) {
        $scope.ends_at = ends_at;
        $scope.timezone = timezone;
        $scope.period = period;
        $scope.refreshTable();
    };

    $scope.refreshTable = function() {
        $scope.query($scope.currentTableData);
    };

    // change the selected tab
    $scope.tabClicked = function(table) {
        $scope.currentTableData = table;
        $scope.refreshTable();
    };

    // open the date picker
    $scope.open = function($event) {
        $event.preventDefault();
        $event.stopPropagation();
        $scope.opened = !$scope.opened;
    };

    $scope.refreshTable();

}]);


importTransactionsControllers.controller("importTransactionsCtrl",
    ["$scope", "$http", "settings",
    function($scope, $http, settings) {
    "use strict";

    // settings for datepicker in angular-ui-bootstrap@2.5.6
    // (https://angular-ui.github.io/bootstrap/#datepicker)
    // The datepicker is used to sed the date an off-line transactions
    // has been created.
    $scope.dateOptions = {
        formatYear: "yyyy",
        initDate: moment().toDate() // today
    };
    $scope.format = "yyyy-MM-dd";

    $scope.opened = {};
    $scope.subscription = null; // XXX really a subscription so far.
    $scope.createdAt = moment().format("YYYY-MM-DD");

    $scope.open = function($event, datePicker) {
        $event.preventDefault();
        $event.stopPropagation();
        $scope.opened[datePicker] = true;
    };

    $scope.getSubscriptions = function(val) {
        return $http.get(settings.urls.organization.api_subscriptions, {
            params: {q: val}
        }).then(function success(resp){
            return resp.data.results;
        });
    };
}]);

/*=============================================================================
  Controller for balance reports
  ============================================================================*/

// directive for a single list
saasApp.directive("saasDndList", function() {
    "use strict";

    return function(scope, element, attrs) {

        // variables used for dnd
        var toUpdate;
        var startIndex = -1;

        // watch the model, so we always know what element
        // is at a specific position
        scope.$watch(attrs.saasDndList, function(value) {
            toUpdate = value;
        }, true);

        // use jquery to make the element sortable (dnd). This is called
        // when the element is rendered
        var $el = $(element[0]);
        if($el.sortable !== undefined){
            $el.sortable({
                items: "tr",
                start: function (event, ui) {
                    // on start we define where the item is dragged from
                    startIndex = ($(ui.item).index());
                },
                stop: function (event, ui) {
                    // on stop we determine the new index of the
                    // item and store it there
                    var newIndex = ($(ui.item).index());
                    scope.saveOrder(startIndex, newIndex);
                },
                axis: "y"
            });
        }
    };
});


// extension to AngularJS to send a PUT request on update instead of a POST.
var balanceResources = angular.module( "balanceResources", [ "ngResource" ] );
balanceResources.factory( "BalanceResource", [ "$resource", function( $resource ) {
    "use strict";
    return function( url, params, methods, options ) {
        var defaults = {
            query: { method: "GET", isArray: false },
            update: { method: "put", isArray: false },
            create: { method: "post" }
        };

        methods = angular.extend( defaults, methods );

        var resource = $resource( url, params, methods, options );

        resource.prototype.$save = function() {
            if ( !this.rank ) {
                this.rank = 0;
                return this.$create();
            }
            else {
                return this.$update();
            }
        };

        return resource;
    };
}]);

var balanceServices = angular.module("balanceServices", ["balanceResources"]);
balanceServices.factory("BalanceLine", ["BalanceResource", "settings",
  function($resource, settings) {
    "use strict";
    return $resource(
        // No slash, it is already part of @path.
        settings.urls.api_balance_lines, {},
        {saveData: {method: "PATCH", isArray: true},
         update: { method: "put", isArray: false,
                   url: settings.urls.api_balance_lines + ":balance",
                   params: {"balance": "@path"}},
        // TODO this is broken (405 method not allowed)
         remove: { method: "delete", isArray: false,
                   url: settings.urls.api_balance_lines + ":balance",
                   params: {"balance": "@path"}},
         create: { method: "POST" }});
  }]);


/*=============================================================================
  Controllers
  ============================================================================*/
var balanceControllers = angular.module("balanceControllers", []);
balanceControllers.controller("BalanceListCtrl",
    ["$scope", "$http", "$filter", "BalanceLine", "settings",
     function($scope, $http, $filter, BalanceLine, settings) {
    "use strict";

    $scope.params = {
        ends_at: moment(settings.date_range.ends_at).toDate(),
        start_at: moment(settings.date_range.start_at).toDate()
    };
    if( !moment($scope.params.ends_at).isValid() ) {
        $scope.params.ends_at = moment().toDate();
    }
    if( !moment($scope.params.start_at).isValid() ) {
        $scope.params.start_at = moment($scope.params.ends_at).subtract(1, "years").toDate();
    }

    // these aren't documented; do they do anything?
    $scope.formats = ["MMM dd, yyyy", "yyyy/MM/dd"];
    $scope.format = $scope.formats[0];
    $scope.dateOptions = {
        formatYear: "yyyy",
        startingDay: 1,
        mode: "month",
        minMode: "month"
    };
    $scope.opened = { "start_at": false, "ends_at": false };
    $scope.timezone = 'local';

    function convertDatetime(data, isUTC){
        // Convert datetime string to moment object in-place because we want
        // to keep extra keys and structure in the JSON returned by the API.
        return data.map(function(f){
            var values = f.values.map(function(v){
                // localizing the period to local browser time
                // unless showing reports in UTC.
                v[0] = isUTC ? moment.parseZone(v[0]) : moment(v[0]);
            });
        });
    };

    $scope.humanizeCell = function(value) {
        return $filter('humanizeCell')(value, $scope.balances.unit, $scope.balances.scale);
    };

    $scope.endOfMonth = function(date) {
        return new Date(
            date.getFullYear(),
            date.getMonth() + 1,
            0
        );
    };

    $scope.open = function($event, datePicker) {
        $event.preventDefault();
        $event.stopPropagation();
        $scope.opened[datePicker] = true;
    };

    $scope.$watch("params", function(newVal, oldVal, scope) {
        if( newVal.start_at !== oldVal.start_at
            && newVal.ends_at === oldVal.ends_at ) {
            if( $scope.params.ends_at < newVal.start_at ) {
                $scope.params.ends_at = newVal.start_at;
            }
        } else if( newVal.start_at === oldVal.start_at
            && newVal.ends_at !== oldVal.ends_at ) {
            if( $scope.params.start_at > newVal.ends_at ) {
                $scope.params.start_at = newVal.ends_at;
            }
        }
        $scope.refresh();
    }, true);

    $scope.newBalanceLine = new BalanceLine();

    $scope.refresh = function() {
        $http.get(settings.urls.api_broker_balances,
            {params: $scope.params}).then(
            function success(resp) {
                convertDatetime(resp.data.table, $scope.timezone === 'utc');
                $scope.balances = resp.data;
                $scope.balances.$resolved = true;
                $scope.startPeriod = moment(resp.data.table[0].values[0][0]).subtract(1, 'months');
            },
            function error(resp) {
                showErrorMessages(resp);
            });
    };
    $scope.refresh();

    $scope.startPeriod = function(date) {
        return moment.subtract(1, 'months');
    }

    $scope.save = function(balance, success) {
        if ( !balance.rank ) {
            balance.rank = 0;
            return BalanceLine.create($scope.params, balance, success,
                function(reps) {
                    showErrorMessages(resp);
                });
        } else {
            return BalanceLine.update(
                $scope.params, balance, success, function(resp) {
                     showErrorMessages(resp);
                });
        }
    };

    $scope.remove = function (idx) {
        BalanceLine.remove({
            balance: $scope.balances.table[idx].path}, function (success) {
                $scope.balances.table.splice(idx, 1);
            });
    };

    $scope.create = function() {
        $scope.save($scope.newBalanceLine, function(result) {
            // success: insert new balance in the list and reset our editor
            // to a new blank.
            $scope.newBalanceLine = new BalanceLine();
            $scope.refresh();
        });
    };

    $scope.saveOrder = function(startIndex, newIndex) {
        BalanceLine.saveData([{oldpos: startIndex, newpos: newIndex}],
            function success(data) {
                $scope.balances = data;
            }, function err(resp) {
                showErrorMessages(resp);
            });
    };
}]);


transactionControllers.controller("accessibleListCtrl",
    ["$scope", "$element", "$controller", "$http", "$timeout", "settings",
    function($scope, $element, $controller, $http, $timeout, settings) {
    "use strict";
    var opts = angular.merge({
        autoload: true,
        sortByField: "slug",
        sortDirection: "asc",
        modalSelector: ".add-role-modal",
        urls: {api_items: settings.urls.user.api_accessibles,
               api_candidates: settings.urls.organization.api_profile_base}}, settings);
    $controller("relationListCtrl", {
        $scope: $scope, $element: $element, $controller: $controller,
        $http: $http, $timeout:$timeout, settings: opts});
}]);


transactionControllers.controller("cartItemListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    var opts = angular.merge({
        autoload: true,
        sortByField: "created_at",
        sortDirection: "desc",
        urls: {api_items: settings.urls.provider.api_metrics_coupon_uses}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: opts});
}]);


transactionControllers.controller("receivableListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    var opts = angular.merge({
        autoload: true,
        sortByField: "created_at",
        sortDirection: "desc",
        urls: {api_items: settings.urls.provider.api_receivables}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: opts});
}]);


transactionControllers.controller("searchListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    var opts = angular.merge({
        urls: {api_items: settings.urls.provider.api_accounts}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: opts});
}]);


transactionControllers.controller("userListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    var opts = angular.merge({
        autoload: true,
        sortByField: "created_at",
        sortDirection: "desc",
        urls: {api_items: settings.urls.provider.api_accounts}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: opts});
}]);


profileControllers.controller("organizationProfileCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {

    $scope.deleteProfile = function(event) {
        event.preventDefault();
        $http.delete(settings.urls.organization.api_base).then(
        function(resp) { // success
            // When we DELETE the request.user profile, it will lead
            // to a logout. When we delete a different profile, a reload
            // of the page leads to a 404. In either cases, moving on
            // to the redirect_to_profile page is a safe bet. */
            window.location = settings.urls.profile_redirect;
        }, function(resp) { // error
            showErrorMessages(resp);
        });
   };

}]);
