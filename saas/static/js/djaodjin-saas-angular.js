/*=============================================================================
  Apps
  ============================================================================*/

angular.module('couponApp', ['ui.bootstrap', 'ngRoute',
    'couponControllers', 'couponServices']);
angular.module('contributorApp', ['ui.bootstrap', 'ngRoute',
    'contributorControllers', 'contributorServices']);
angular.module('managerApp', ['ui.bootstrap', 'ngRoute',
    'managerControllers', 'managerServices']);
angular.module('subscriptionApp', ['ui.bootstrap', 'ngRoute',
    'subscriptionControllers', 'subscriptionServices']);
angular.module('subscriberApp', ['ui.bootstrap', 'ngRoute',
    'subscriberControllers']);


/*=============================================================================
  Services
  ============================================================================*/

var couponServices = angular.module('couponServices', ['ngResource']);
var contributorServices = angular.module('contributorServices', ['ngResource']);
var managerServices = angular.module('managerServices', ['ngResource']);
var subscriptionServices = angular.module('subscriptionServices', [
    'ngResource']);


couponServices.factory('Coupon', ['$resource', 'urls',
  function($resource, urls){
    return $resource(
        urls.saas_api_coupon_url + '/:coupon', {'coupon':'@code'},
            {create: {method:'POST'},
             update: {method:'PUT', isArray:false}});
  }]);

contributorServices.factory('Contributor', ['$resource', 'urls',
  function($resource, urls){
    return $resource(
        urls.saas_api_contributor_url + '/:user', {'user':'@user'});
  }]);

managerServices.factory('Manager', ['$resource', 'urls',
  function($resource, urls){
    return $resource(
        urls.saas_api_manager_url + '/:user', {'user':'@user'});
  }]);

subscriptionServices.factory('Subscription', ['$resource', 'urls',
  function($resource, urls){
    return $resource(
        urls.saas_api_subscription_url + '/:plan', {plan:'@plan'});
  }]);

/*=============================================================================
  Controllers
  ============================================================================*/

var couponControllers = angular.module('couponControllers', []);
var contributorControllers = angular.module('contributorControllers', []);
var managerControllers = angular.module('managerControllers', []);
var subscriptionControllers = angular.module('subscriptionControllers', []);
var subscriberControllers = angular.module('subscriberControllers', []);

couponControllers.controller('CouponListCtrl',
    ['$scope', '$http', '$timeout', 'Coupon', 'urls',
     function($scope, $http, $timeout, Coupon, urls) {
    $scope.urls = urls;
    $scope.dir = {code: 'asc'};
    $scope.params = {o: 'code', ot: $scope.dir['code']};
    $scope.coupons = Coupon.query($scope.params);
    $scope.newCoupon = new Coupon();

    $scope.filterExpr = '';
    $scope.maxSize = 10;  // Limit number for pagination size
    $scope.numPages = 5;  // Total number of pages to display
    $scope.currentPage = 1;

    $scope.dateOptions = {
        formatYear: 'yy',
        startingDay: 1
    };

    $scope.initDate = new Date('2016-15-20');
    $scope.minDate = new Date();
    $scope.maxDate = new Date('2016-01-01');
    $scope.formats = ['dd-MMMM-yyyy', 'yyyy/MM/dd', 'dd.MM.yyyy', 'shortDate'];
    $scope.format = $scope.formats[0];

    $scope.filterList = function(regex) {
        console.log("filterExp:", regex);
        if( regex ) {
            $scope.params['q'] = regex;
        } else {
            delete $scope.params['q'];
        }
        $scope.coupons = Coupon.query($scope.params);
    };

    // calendar for expiration date
    $scope.open = function($event, coupon) {
        $event.preventDefault();
        $event.stopPropagation();
        coupon.opened = true;
    };

    $scope.pageChanged = function() {
        if( $scope.currentPage > 1 ) {
            $scope.params['offset'] = ($scope.currentPage - 1) * $scope.maxSize;
        }
        $scope.coupons = Coupon.query($scope.params);
    };

    $scope.remove = function (idx) {
        Coupon.remove({ coupon: $scope.coupons[idx].code }, function (success) {
            $scope.coupons.splice(idx, 1);
        });
    };

    $scope.save = function() {
        $http.post(urls.saas_api_coupon_url,$scope.newCoupon).success(
        function(result) {
            $scope.coupons.push(new Coupon(result));
            // Reset our editor to a new blank post
            $scope.newCoupon = new Coupon();
        });
    };

    $scope.sortBy = function(fieldName) {
        if( $scope.dir[fieldName] == 'asc' ) {
            $scope.dir = {};
            $scope.dir[fieldName] = 'desc';
        } else {
            $scope.dir = {};
            $scope.dir[fieldName] = 'asc';
        }
        $scope.params['o'] = fieldName;
        $scope.params['ot'] = $scope.dir[fieldName];
        $scope.coupons = Coupon.query($scope.params);
    }

    $scope.$watch('coupons', function(newVal, oldVal, scope) {
        var length = ( oldVal.length < newVal.length ) ?
            oldVal.length : newVal.length;
        for( var i = 0; i < length; ++i ) {
            if( oldVal[i].ends_at != newVal[i].ends_at ) {
                newVal[i].$update().then(function(result) {
                    // XXX message expiration date was updated.
                });
            }
        }
    }, true);

    $scope.editDescription = function (idx){
        $scope.edit_description = Array.apply(null, Array($scope.coupons.length)).map(function() {
            return false;
        });
        $scope.edit_description[idx] = true;
        $timeout(function(){
            angular.element('#input_description').focus();
        }, 100);
    };

    $scope.saveDescription = function(event, coupon, idx){
        if (event.which === 13 || event.type == 'blur' ){
            $scope.edit_description[idx] = false;
            coupon.$update();
        }
    };
}]);


contributorControllers.controller('contributorListCtrl',
    ['$scope', '$http', 'Contributor', 'urls',
    function($scope, $http, Contributor, urls) {

    $scope.users = Contributor.query();

    $scope.user = null;

    $scope.remove = function (idx) {
        Contributor.remove({ user: $scope.users[idx].username },
        function (success) {
            $scope.users.splice(idx, 1);
        });
    };

    $scope.save = function() {
        (new Contributor($scope.user)).$save(
            function(success) {
                /* XXX Couldn't figure out how to get the status code
                   here so we just reload the list. */
                $scope.users = Contributor.query();
            },
            function(error) {});
    };

    $scope.getUsers = function(val) {
        return $http.get(urls.saas_api_user_url, {
            params: {q: val}
        }).then(function(res){
            return res.data;
        });
    };

}]);


managerControllers.controller('managerListCtrl',
    ['$scope', '$http', 'Manager', 'urls',
    function($scope, $http, Manager, urls) {

    $scope.users = Manager.query();

    $scope.user = null;

    $scope.remove = function (idx) {
        Manager.remove({ user: $scope.users[idx].username },
        function (success) {
            $scope.users.splice(idx, 1);
        });
    };

    $scope.save = function() {
        (new Manager($scope.user)).$save(
            function(success) {
                /* XXX Couldn't figure out how to get the status code
                   here so we just reload the list. */
                $scope.users = Manager.query();
            },
            function(error) {});
    };

    $scope.getUsers = function(val) {
        return $http.get(urls.saas_api_user_url, {
            params: {q: val}
        }).then(function(res){
            return res.data;
        });
    };

}]);

subscriptionControllers.controller('subscriptionListCtrl',
    ['$scope', '$http', 'Subscription', 'urls',
    function($scope, $http, Subscription, urls) {

    $scope.unsubscribe = function(url) {
        if( confirm("Are you sure?") ) {
            $http.$delete(url).then(function(data){ location.reload(); });
        }
    }
}]);

subscriberControllers.controller('subscriberCtrl',
    ['$scope', '$http', 'urls',
    function($scope, $http, urls) {

    $scope.opened = { 'start_at': false, 'ends_at': false }
    $scope.start_at = new Date();
    $scope.ends_at = new Date();

    $scope.minDate = new Date('2014-01-01');
    $scope.maxDate = new Date('2016-01-01');
    $scope.dateOptions = {formatYear: 'yy', startingDay: 1};
    $scope.formats = ['dd-MMMM-yyyy', 'yyyy/MM/dd', 'dd.MM.yyyy', 'shortDate'];
    $scope.format = $scope.formats[0];

    // initialized with *maxSize* empty items for layout during first load.
    $scope.registered = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];
    $scope.subscribed = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];
    $scope.churned = [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}];

    $scope.maxSize = 10;  // Limit number for pagination size
    $scope.numPages = 5;  // Total number of pages to display
    $scope.currentPage = {churned: 1, registered: 1, subscribed: 1};

    // calendar for start_at and ends_at
    $scope.open = function($event, date_at) {
        $event.preventDefault();
        $event.stopPropagation();
        $scope.opened[date_at] = true;
    };

    // XXX start_at and ends_at will be both updated on reload
    //     which will lead to two calls to the backend instead of one.
    $scope.$watch('start_at', function(newVal, oldVal, scope) {
        if( $scope.ends_at < newVal ) {
            $scope.ends_at = newVal;
        }
        $scope.refresh();
    }, true);

    $scope.$watch('ends_at', function(newVal, oldVal, scope) {
        if( $scope.start_at > newVal ) {
            $scope.start_at = newVal;
        }
        $scope.refresh();
    }, true);

    $scope.pageChanged = function(dataset) {
        $scope.refresh(dataset);
    };

    $scope.refresh = function(dataset) {
        if( typeof dataset === "undefined" || dataset == 'churned' ) {
            params = {start_at: $scope.start_at, ends_at: $scope.ends_at};
            if( $scope.currentPage.churned > 1 ) {
                params['offset'] = ($scope.currentPage.churned - 1)
                    * $scope.maxSize;
            }
            $http.get(urls.saas_api_churned, {
                params: params
            }).success(function(data) {
                $scope.churned = data;
                for( var i = $scope.churned.churned.length;
                     i < $scope.maxSize; ++i ) {
                    $scope.churned.churned.push({});
                }
            });
        }
        if( typeof dataset === "undefined" || dataset == 'registered' ) {
            params = {start_at: $scope.start_at, ends_at: $scope.ends_at};
            if( $scope.currentPage.registered > 1 ) {
                params['offset'] = ($scope.currentPage.registered - 1)
                    * $scope.maxSize;
            }
            $http.get(urls.saas_api_registered, {
                params: params
            }).success(function(data) {
                $scope.registered = data;
                for( var i = $scope.registered.registered.length;
                     i < $scope.maxSize; ++i ) {
                    $scope.registered.registered.push({});
                }
            });
        }
        if( typeof dataset === "undefined" || dataset == 'subscribed' ) {
            params = {start_at: $scope.start_at, ends_at: $scope.ends_at};
            if( $scope.currentPage.subscribed > 1 ) {
                params['offset'] = ($scope.currentPage.subscribed - 1)
                    * $scope.maxSize;
            }
            $http.get(urls.saas_api_subscribed, {
                params: params
            }).success(function(data) {
                $scope.subscribed = data;
                for( var i = $scope.subscribed.subscribed.length;
                     i < $scope.maxSize; ++i ) {
                    $scope.subscribed.subscribed.push({});
                }
            });
        }
    }

    $scope.endsSoon = function(organization) {
        var cutOff = new Date($scope.ends_at);
        cutOff.setDate($scope.ends_at.getDate() + 5);
        for( var i = 0; i < organization.subscriptions.length; ++i ) {
            var sub = organization.subscriptions[i];
            var subEndsAt = new Date(sub.ends_at);
            if( subEndsAt < cutOff ) {
                return "ends-soon";
            }
        }
        return "";
    }
}]);

