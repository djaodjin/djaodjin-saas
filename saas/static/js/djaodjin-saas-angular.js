/*=============================================================================
  Apps
  ============================================================================*/

var saasApp = angular.module("saasApp", [
    "ui.bootstrap", "ngDragDrop", "ngRoute",
    "balanceControllers", "balanceServices",
    "couponControllers", "couponServices",
    "metricsControllers",
    "importTransactionsControllers",
    "subscriptionControllers",
    "transactionControllers", "saasFilters"]);

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

        var current = moment();
        return function(datestr) {
            var date = moment(datestr);
            var heading = date.format("MMM'YY");
            if( date > current ) {
                // add incomplete month marker
                heading += "*";
            }
            return heading;
        };
    })
    .filter("humanizeCell", function(currencyFilter, numberFilter) {
        "use strict";

        return function(cell, unit, scale, abbreviate) {
            if(typeof abbreviate === "undefined"){
                abbreviate = true;
            }
            scale = scale || 1;
            var value = cell * scale;
            if(unit) {
                if( unit === 'usd' ) { unit = '$' }
                return currencyFilter(value, unit, 2);
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
}]);

/*=============================================================================
  Services
  ============================================================================*/
var couponServices = angular.module("couponServices", ["ngResource"]);


couponServices.factory("Coupon", ["$resource", "settings",
  function($resource, settings){
    "use strict";
    return $resource(
        settings.urls.saas_api_coupon_url + "/:coupon", {coupon: "@code"},
            {query: {method: "GET"},
             create: {method: "POST"},
             update: {method: "PUT", isArray: false}});
  }]);


//=============================================================================
// Controllers
//============================================================================

var couponControllers = angular.module("couponControllers", []);
var subscriptionControllers = angular.module("subscriptionControllers", []);
var transactionControllers = angular.module("transactionControllers", []);
var metricsControllers = angular.module("metricsControllers", []);
var importTransactionsControllers = angular.module("importTransactionsControllers", []);


transactionControllers.controller("itemsListCtrl",
    ["$scope", "$http", "$timeout", "settings",
     function($scope, $http, $timeout, settings) {
    "use strict";
    $scope.items = {};
    $scope.totalItems = 0;

    $scope.resetDefaults = function(overrides) {
        $scope.dir = {};
        var opts = {};
        if( settings.sortByField ) {
            opts['o'] = settings.sortByField;
            opts['ot'] = settings.sortDirection || "desc";
            $scope.dir[settings.sortByField] = opts['ot'];
        }
        if( settings.date_range ) {
            if( settings.date_range.start_at ) {
                opts['start_at'] = moment(settings.date_range.start_at).toDate();
            }
            if( settings.date_range.ends_at ) {
                opts['ends_at'] = moment(settings.date_range.ends_at).toDate()
            }
        }
        $scope.filterExpr = "";
        $scope.itemsPerPage = settings.itemsPerPage; // Must match server-side
        $scope.maxSize = 5;               // Total number of direct pages link
        $scope.currentPage = 1;
        // currentPage will be saturated at maxSize when maxSize is defined.
        $scope.formats = ["dd-MMMM-yyyy", "yyyy/MM/dd",
            "dd.MM.yyyy", "shortDate"];
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
        $scope.opened[date_at] = true;
    };

    // Generate a relative date for an instance with a ``created_at`` field.
    $scope.relativeDate = function(at_time) {
        var cutOff = new Date();
        if( $scope.params.ends_at ) {
            cutOff = new Date($scope.params.ends_at);
        }
        var dateTime = new Date(at_time);
        if( dateTime <= cutOff ) {
            return moment.duration(cutOff - dateTime).humanize() + " ago";
        } else {
            return moment.duration(dateTime - cutOff).humanize() + " left";
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

    $scope.pageChanged = function() {
        if( $scope.currentPage > 1 ) {
            $scope.params.page = $scope.currentPage;
        } else {
            delete $scope.params.page;
        }
    };

    $scope.sortBy = function(fieldName) {
        if( $scope.dir[fieldName] == "asc" ) {
            $scope.dir = {};
            $scope.dir[fieldName] = "desc";
        } else {
            $scope.dir = {};
            $scope.dir[fieldName] = "asc";
        }
        $scope.params.o = fieldName;
        $scope.params.ot = $scope.dir[fieldName];
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

    $scope.item = null;

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
        if( !$scope.item ) {
            $scope.item = {};
        }
        if( !$scope.item.hasOwnProperty('email')
              || typeof $scope.item.email === "undefined" ) {
            $scope.item.email = emailField.val();
        }
        $scope.item.message = dialog.find("[name='message']").val();
        $http.post(settings.urls.api_items + "?force=1", $scope.item).then(
            function success(resp) {
                // XXX Couldn't figure out how to get the status code
                //   here so we just reload the list.
                $scope.refresh();
                $scope.item = null;
            },
            function error(resp) {
                showErrorMessages(resp);
            });
    };

    $scope.save = function($event, item) {
        $event.preventDefault();
        if( typeof item !== "undefined" ) {
            $scope.item = item;
        }
        $http.post(settings.urls.api_items, $scope.item).then(
            function(success) {
                // XXX Couldn't figure out how to get the status code
                // here so we just reload the list.
                $scope.refresh();
                $scope.item = null;
            },
            function(resp) {
                if( resp.status === 404 ) {
                    // XXX hack to set full_name when org does not exist.
                    $scope.item.full_name = $scope.item.slug;
                    // XXX hack to set email when user does not exist.
                    $scope.item.email = $scope.item.slug;
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


couponControllers.controller("CouponListCtrl",
    ["$scope", "$http", "$timeout", "Coupon", "settings",
     function($scope, $http, $timeout, Coupon, settings) {
    "use strict";
    $scope.totalItems = 0;
    $scope.dir = {code: "asc"};
    $scope.params = {o: "code", ot: $scope.dir.code};
    $scope.coupons = Coupon.query($scope.params, function() {
        // We cannot watch coupons.count otherwise things start
        // to snowball. We must update totalItems only when it truly changed.
        if( $scope.coupons.count !== $scope.totalItems ) {
            $scope.totalItems = $scope.coupons.count;
        }
    });
    $scope.newCoupon = new Coupon();

    $scope.filterExpr = "";
    $scope.itemsPerPage = settings.itemsPerPage; // Must match server-side
    $scope.maxSize = 5;               // Total number of direct pages link
    $scope.currentPage = 1;

    $scope.dateOptions = {
        formatYear: "yy",
        startingDay: 1
    };

    $scope.initDate = new Date("2018-01-01");
    $scope.minDate = new Date();
    $scope.maxDate = new Date("2018-01-01");
    $scope.formats = ["dd-MMMM-yyyy", "yyyy/MM/dd", "dd.MM.yyyy", "shortDate"];
    $scope.format = $scope.formats[0];

    $scope.filterList = function(regex) {
        if( regex ) {
            if ("page" in $scope.params){
                delete $scope.params.page;
            }
            $scope.params.q = regex;
        } else {
            delete $scope.params.q;
        }
        $scope.coupons = Coupon.query($scope.params, function() {
            if( $scope.coupons.count !== $scope.totalItems ) {
                $scope.totalItems = $scope.coupons.count;
            }
        });
    };

    // calendar for expiration date
    $scope.open = function($event, coupon) {
        $event.preventDefault();
        $event.stopPropagation();
        coupon.opened = true;
    };

    $scope.pageChanged = function() {
        if( $scope.currentPage > 1 ) {
            $scope.params.page = $scope.currentPage;
        } else {
            delete $scope.params.page;
        }
        $scope.coupons = Coupon.query($scope.params, function() {
            if( $scope.coupons.count !== $scope.totalItems ) {
                $scope.totalItems = $scope.coupons.count;
            }
        });
    };

    $scope.remove = function (idx) {
        Coupon.remove({ coupon: $scope.coupons.results[idx].code },
        function (success) {
            $scope.coupons = Coupon.query($scope.params, function() {
                if( $scope.coupons.count !== $scope.totalItems ) {
                    $scope.totalItems = $scope.coupons.count;
                }
            });
        });
    };

    $scope.save = function() {
        $http.post(settings.urls.saas_api_coupon_url, $scope.newCoupon).then(
        function success(resp) {
            $scope.coupons.results.push(new Coupon(resp.data));
            // Reset our editor to a new blank post
            $scope.newCoupon = new Coupon();
        }, function error(resp){
            showErrorMessages(resp);
        });
    };

    $scope.sortBy = function(fieldName) {
        if( $scope.dir[fieldName] === "asc" ) {
            $scope.dir = {};
            $scope.dir[fieldName] = "desc";
        } else {
            $scope.dir = {};
            $scope.dir[fieldName] = "asc";
        }
        $scope.params.o = fieldName;
        $scope.params.ot = $scope.dir[fieldName];
        $scope.currentPage = 1;
        // pageChanged only called on click?
        delete $scope.params.page;
        $scope.coupons = Coupon.query($scope.params, function() {
            if( $scope.coupons.count !== $scope.totalItems ) {
                $scope.totalItems = $scope.coupons.count;
            }
        });
    };

    $scope.$watch("coupons", function(newVal, oldVal, scope) {
        if( newVal.hasOwnProperty("results") &&
            oldVal.hasOwnProperty("results") ) {
            var length = ( oldVal.results.length < newVal.results.length ) ?
                oldVal.results.length : newVal.results.length;
            for( var i = 0; i < length; ++i ) {
                if( (oldVal.results[i].ends_at !== newVal.results[i].ends_at)
                    || (oldVal.results[i].description !== newVal.results[i].description)) {
                    Coupon.update(newVal.results[i], function(result) {
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
            null, new Array($scope.coupons.results.length)).map(function() {
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
        : settings.urls.saas_api_user_roles_url;
    var opts = angular.merge({
        autoload: true,
        sortByField: "username",
        sortDirection: "desc",
        modalSelector: ".add-role-modal",
        urls: {api_items: apiUrl,
               api_candidates: settings.urls.api_users}}, settings);
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
        urls: {api_items: settings.urls.saas_api_role_descriptions_url}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout: $timeout,
        settings: opts});

    $scope.addRoleDescription = function() {
        $scope.newRoleDescription = null;
        var dialog = angular.element("#new-role-description");
    };

    $scope.createRoleDescription = function() {
        $http.post(settings.urls.saas_api_role_descriptions_url,
                   $scope.newRoleDescription).then(function() {
            var dialog = angular.element("#new-role-description");
            if (dialog.data("bs.modal")) {
                dialog.modal("hide");
            }
            $scope.refresh();
        });
    };

    $scope.deleteRoleDescription = function(roleDescription) {
        var url = settings.urls.saas_api_role_descriptions_url +
                  "/" + roleDescription.slug;

        $http.delete(url).then(function() {
            $scope.refresh();
        });
    }
}]);


subscriptionControllers.controller("subscriptionListCtrl",
    ["$scope", "$http", "$timeout", "settings",
    function($scope, $http, $timeout, settings) {
    "use strict";
    var defaultSortByField = "created_at";
    $scope.dir = {};
    $scope.dir[defaultSortByField] = "desc";
    $scope.params = {o: defaultSortByField, ot: $scope.dir[defaultSortByField]};

    $scope.filterExpr = "";
    $scope.itemsPerPage = settings.itemsPerPage; // Must match server-side
    $scope.maxSize = 5;               // Total number of direct pages link
    $scope.currentPage = 1;

    $scope.dateOptions = {
        formatYear: "yy",
        startingDay: 1
    };

    $scope.initDate = new Date("2018-01-01");
    $scope.minDate = new Date();
    $scope.maxDate = new Date("2018-01-01");
    $scope.formats = ["dd-MMMM-yyyy", "yyyy/MM/dd", "dd.MM.yyyy", "shortDate"];
    $scope.format = $scope.formats[0];
    $scope.ends_at = moment().endOf("day").toDate();

    $scope.registered = {
        $resolved: false, count: 0,
        location: settings.urls.api_registered};
    $scope.subscribed = {
        $resolved: false, count: 0,
        location: settings.urls.saas_api_subscriptions};
    $scope.churned = {
        $resolved: false, count: 0,
        location: settings.urls.saas_api_churned};

    $scope.active = $scope.subscribed;

    // Returns ends-soon when the subscription is about to end.
    $scope.endsSoon = function(subscription) {
        var cutOff = new Date($scope.ends_at);
        cutOff.setDate($scope.ends_at.getDate() + 5);
        var subEndsAt = new Date(subscription.ends_at);
        if( subEndsAt < cutOff ) {
            return "ends-soon";
        }
        return "";
    };

    $scope.query = function(queryset) {
        queryset.$resolved = false;
        queryset.results = [];
        $http.get(queryset.location, {params: $scope.params}).then(
        function success(resp) {
            queryset.results = resp.data.results;
            queryset.count = resp.data.count;
            queryset.$resolved = true;
        });
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
            $http.patch(settings.urls.api_organizations
                + entry.organization.slug + "/subscriptions/" + entry.plan.slug,
                {description: entry.description}).then(
                function(data){
                    // XXX message expiration date was updated.
            });
        }
    };

    $scope.filterList = function(regex) {
        if( regex ) {
            if ("page" in $scope.params){
                delete $scope.params.page;
            }
            $scope.params.q = regex;
        } else {
            delete $scope.params.q;
        }
        $scope.query($scope.active);
    };

    $scope.pageChanged = function(queryset) {
        if( $scope.currentPage > 1 ) {
            $scope.params.page = $scope.currentPage;
        } else {
            delete $scope.params.page;
        }
        $scope.query(queryset);
    };

    $scope.prefetch = function() {
      $scope.query($scope.registered);
      $scope.query($scope.churned);
    };

    // Generate a relative date for an instance with a ``created_at`` field.
    $scope.relativeDate = function(at_time) {
        var cutOff = new Date($scope.ends_at);
        var dateTime = new Date(at_time);
        if( dateTime <= cutOff ) {
            return moment.duration(cutOff - dateTime).humanize() + " ago";
        } else {
            return moment.duration(dateTime - cutOff).humanize() + " left";
        }
    };

    $scope.sortBy = function(fieldName) {
        if( $scope.dir[fieldName] === "asc" ) {
            $scope.dir = {};
            $scope.dir[fieldName] = "desc";
        } else {
            $scope.dir = {};
            $scope.dir[fieldName] = "asc";
        }
        $scope.params.o = fieldName;
        $scope.params.ot = $scope.dir[fieldName];
        $scope.currentPage = 1;
        // pageChanged only called on click?
        delete $scope.paramspage;
        $scope.query($scope.active);
    };

    // Change the active tab.
    // XXX We need this method because filters are "global" accross all tabs.
    $scope.tabClicked = function($event) {
        var newActiveTab = $event.target.getAttribute("href").replace(/^#/, "");
        if( newActiveTab === "registered-users" ) {
            if( !$scope.registered.hasOwnProperty("results") ) {
                $scope.query($scope.registered);
            }
            $scope.active = $scope.registered;
        } else if( newActiveTab === "subscribed" ) {
            if( !$scope.subscribed.hasOwnProperty("results") ) {
                $scope.query($scope.subscribed);
            }
            $scope.active = $scope.subscribed;
        } else if( newActiveTab === "churned" ) {
            if( !$scope.churned.hasOwnProperty("results") ) {
                $scope.query($scope.churned);
            }
            $scope.active = $scope.churned;
        }
    };

    $scope.unsubscribe = function(organization, plan) {
        if( confirm("Are you sure?") ) {
            $http.delete(settings.urls.api_organizations
                + organization + "/subscriptions/" + plan).then(
            function() {
                $scope.query($scope.active);
            });
        }
    };

    $scope.query($scope.subscribed);
}]);

subscriptionControllers.controller("subscriberListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    settings.urls.saas_api_subscriptions = settings.urls.saas_api_active_subscribers;
    $controller('subscriptionListCtrl', {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: settings});
}]);


transactionControllers.controller("transactionListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    var opts = angular.merge({
        autoload: true,
        sortByField: "created_at",
        sortDirection: "desc",
        urls: {api_items: settings.urls.api_transactions}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: opts});
}]);


transactionControllers.controller("billingStatementCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    $scope.cancelBalance = function($event) {
        $event.preventDefault();
        $http.delete(settings.urls.api_cancel_balance_due).then(
            function success(resp) {
                $scope.resetDefaults({'ends_at': moment().toDate()});
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
    ["$scope", "$attrs", "$controller", "$http", "$timeout", "settings",
    function($scope, $attrs, $controller, $http, $timeout, settings) {
    "use strict";
    var apiUrl = $attrs.apiUrl ? $attrs.apiUrl : settings.urls.saas_api_bank;

    $scope.last4 = "N/A";
    $scope.exp_date = "N/A";
    $scope.bank_name = "N/A";
    $scope.balance_amount = "N/A";

    if( apiUrl ) {
        $http.get(apiUrl).then(
        function success(resp) {
            $scope.balance_amount = resp.data.balance_amount;
            $scope.balance_unit = resp.data.balance_unit;
            $scope.last4 = resp.data.last4;
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
        urls: {api_items: settings.urls.api_charges}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: opts});
}]);


metricsControllers.controller("metricsCtrl",
    ["$scope", "$http", "settings",
    function($scope, $http, settings) {
    "use strict";

    $scope.tables = settings.tables;
    $scope.tabs = [];
    for( var i = 0; i < $scope.tables.length; ++i ) {
        $scope.tabs.push($scope.tables[i].key);
    }
    $scope.activeTab = $scope.tabs[0];

    $scope.endOfMonth = function(date) {
        return new Date(
            date.getFullYear(),
            date.getMonth() + 1,
            0
        );
    };

    $scope.ends_at = moment(settings.date_range.ends_at);
    if( $scope.ends_at.isValid() ) {
        $scope.ends_at = $scope.ends_at.toDate();
    } else {
        $scope.ends_at = moment().toDate();
    }

    // these aren't documented; do they do anything?
    $scope.formats = ["MM-yyyy", "yyyy/MM", "MM.yyyy"];
    $scope.format = $scope.formats[0];
    $scope.dateOptions = {
        formatYear: "yyyy",
        startingDay: 1,
        mode: "month",
        minMode: "month"
    };
    $scope.opened = false;

    $scope.getTable = function(key) {
        for( var i = 0; i < $scope.tables.length; ++i ) {
            if( $scope.tables[i].key === key ) {
                return $scope.tables[i];
            }
        }
        return null;
    };

    $scope.prefetch = function() {
        for( var i = 0; i < $scope.tables.length; ++i ) {
            $scope.query($scope.tables[i]);
        }
    };

    $scope.query = function(queryset) {
        $http.get(
            queryset.location, {params: {"ends_at": $scope.ends_at}}).then(
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

            // manual binding - trigger updates to the graph
            if( queryset.key === "balances") {
                // XXX Hard-coded.
                updateBarChart("#metrics-chart",
                               resp.data.table, unit, scale, extra);
            } else {
                updateChart("#metrics-chart",
                            resp.data.table, unit, scale, extra);
            }
        });
    };

    $scope.refreshTable = function() {
        $scope.query($scope.getTable($scope.activeTab));
    };

    // change the selected tab
    $scope.tabClicked = function($event) {
        $scope.activeTab = $event.target.getAttribute("href").replace(/^#/, "");
        $scope.refreshTable();
    };

    // open the date picker
    $scope.open = function($event) {
        $event.preventDefault();
        $event.stopPropagation();
        $scope.opened = true;
    };

    $scope.$watch("ends_at", function(newVal, oldVal, scope) {
        if (newVal !== oldVal) {
            $scope.ends_at = $scope.endOfMonth(newVal);
            $scope.refreshTable();
        }
    }, true);

    $scope.refreshTable();

}]);


importTransactionsControllers.controller("importTransactionsCtrl",
    ["$scope", "$http", "settings",
    function($scope, $http, settings) {
    "use strict";

    // these aren't documented; do they do anything?
    $scope.formats = ["yyyy-MM-dd", "shortDate"];
    $scope.format = $scope.formats[0];
    $scope.dateOptions = {
        formatYear: "yyyy",
        startingDay: 1
    };
    $scope.minDate = new Date('2015-01-01');
    $scope.maxDate = new Date('2018-01-01');
    $scope.opened = {};

    $scope.subscription = null; // XXX really a subscription so far.
    $scope.createdAt = moment().format("YYYY-MM-DD");

    $scope.open = function($event, datePicker) {
        $event.preventDefault();
        $event.stopPropagation();
        $scope.opened[datePicker] = true;
    };

    $scope.getSubscriptions = function(val) {
        return $http.get(settings.urls.saas_api_subscriptions, {
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
        scope.$watch(attrs.dndList, function(value) {
            toUpdate = value;
        }, true);

        // use jquery to make the element sortable (dnd). This is called
        // when the element is rendered
        $(element[0]).sortable({
            items: "tr",
            start: function (event, ui) {
                // on start we define where the item is dragged from
                startIndex = ($(ui.item).index());
            },
            stop: function (event, ui) {
                // on stop we determine the new index of the
                // item and store it there
                var newIndex = ($(ui.item).index());
                var oldRank = toUpdate[startIndex].rank;
                var newRank = toUpdate[newIndex].rank;
                scope.saveOrder(oldRank, newRank);
            },
            axis: "y"
        });
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
    ["$scope", "$http", "BalanceLine", "settings",
     function($scope, $http, BalanceLine, settings) {
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
    $scope.formats = ["MM-yyyy", "yyyy/MM", "MM.yyyy"];
    $scope.format = $scope.formats[0];
    $scope.dateOptions = {
        formatYear: "yyyy",
        startingDay: 1,
        mode: "month",
        minMode: "month"
    };
    $scope.opened = { "start_at": false, "ends_at": false };

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
            balance: $scope.balances.results[idx].path}, function (success) {
                $scope.balances.results.splice(idx, 1);
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
        urls: {api_items: settings.urls.api_accessibles,
               api_candidates: settings.urls.api_organizations}}, settings);
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
        urls: {api_items: settings.urls.api_metrics_coupon_uses}}, settings);
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
        urls: {api_items: settings.urls.api_receivables}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: opts});
}]);


transactionControllers.controller("searchListCtrl",
    ["$scope", "$controller", "$http", "$timeout", "settings",
    function($scope, $controller, $http, $timeout, settings) {
    var opts = angular.merge({
        urls: {api_items: settings.urls.api_accounts}}, settings);
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
        urls: {api_items: settings.urls.api_accounts}}, settings);
    $controller("itemsListCtrl", {
        $scope: $scope, $http: $http, $timeout:$timeout,
        settings: opts});
}]);
