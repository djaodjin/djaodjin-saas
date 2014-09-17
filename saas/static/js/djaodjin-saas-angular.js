/*=============================================================================
  Apps
  ============================================================================*/

angular.module('couponApp', ['ngRoute', 'couponControllers', 'couponServices']);
angular.module('contributorApp', ['ngRoute',
    'contributorControllers', 'contributorServices']);
angular.module('managerApp', ['ngRoute', 'managerControllers',
    'managerServices']);
angular.module('subscriptionApp', ['ngRoute', 'subscriptionControllers',
    'subscriptionServices']);


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
        urls.saas_api_coupon_url + '/:coupon', { 'coupon':'@coupon'});
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

couponControllers.controller('CouponListCtrl',
    ['$scope', '$http', 'Coupon', 'urls',
     function($scope, $http, Coupon, urls) {
    $scope.urls = urls;
    $scope.coupons = Coupon.query();

    $scope.newCoupon = new Coupon()

    $scope.remove = function (idx) {
        Coupon.remove({ coupon: $scope.coupons[idx].code }, function (success) {
            $scope.coupons.splice(idx, 1);
        });
    }

    $scope.save = function() {
        $scope.newCoupon.$save().then(function(result) {
            $scope.coupons.push(result);
        }).then(function() {
            // Reset our editor to a new blank post
            $scope.newCoupon = new Coupon()
        });
    }
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

